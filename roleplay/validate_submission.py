#!/usr/bin/env python3
"""Validate the exact 571-record CharacterEval OJ submission format."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "基于大模型的角色扮演" / "test_data.jsonl"
MAX_BYTES = 10 * 1024 * 1024
MAX_CHARS = 20000


def check(path: Path, source: Path = DATA) -> dict:
    ground = json.loads(source.read_text(encoding="utf-8"))
    assert isinstance(ground, list) and len(ground) == 571, "Expected 571 original test examples"
    ids = {str(x["id"]) for x in ground}
    assert len(ids) == 571, "Duplicate source IDs"
    assert path.stat().st_size <= MAX_BYTES, "Submission exceeds 10 MiB"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list), "Submission must be a top-level JSON array"
    seen = set()
    for i, row in enumerate(data):
        assert isinstance(row, dict), f"row {i} must be an object"
        assert set(row) == {"id", "model_output"}, f"row {i}: unexpected/missing keys"
        rid = str(row["id"])
        assert rid in ids, f"row {i}: unknown ID {rid}"
        assert rid not in seen, f"row {i}: duplicate ID {rid}"
        seen.add(rid)
        val = row["model_output"]
        assert isinstance(val, str), f"ID {rid}: model_output must be string"
        assert len(val) <= MAX_CHARS, f"ID {rid}: response over 20000 chars"
        first_line = val.splitlines()[0].strip() if val.splitlines() else ""
        assert first_line and first_line != "ERROR", f"ID {rid}: invalid first line"
        assert "\n" not in val and "\r" not in val, f"ID {rid}: output must be one line"
    assert seen == ids, f"Coverage incomplete: {len(seen)}/571; missing={sorted(ids-seen)[:15]}"
    return {"records": len(data), "bytes": path.stat().st_size, "unique_ids": len(seen)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("submission", type=Path)
    ap.add_argument("--source", type=Path, default=DATA)
    args = ap.parse_args()
    print(json.dumps(check(args.submission, args.source), ensure_ascii=False, indent=2))
