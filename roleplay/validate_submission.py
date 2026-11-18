#!/usr/bin/env python3
"""Validate the exact 571-record CharacterEval OJ submission format."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "基于大模型的角色扮演" / "test_data.jsonl"
MAX_BYTES = 10 * 1024 * 1024
MAX_CHARS = 20000


def require(condition, message):
    # Unlike assert, validation must remain active under python -O.
    if not condition:
        raise ValueError(message)


def check(path: Path, source: Path = DATA) -> dict:
    ground = json.loads(source.read_text(encoding="utf-8"))
    require(isinstance(ground, list) and len(ground) == 571, "Expected 571 original test examples")
    ids = {str(x["id"]) for x in ground}
    require(len(ids) == 571, "Duplicate source IDs")
    require(path.stat().st_size <= MAX_BYTES, "Submission exceeds 10 MiB")
    data = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(data, list), "Submission must be a top-level JSON array")
    seen = set()
    for i, row in enumerate(data):
        require(isinstance(row, dict), f"row {i} must be an object")
        require(set(row) == {"id", "model_output"}, f"row {i}: unexpected/missing keys")
        require(type(row["id"]) in (int, str), f"row {i}: ID must be integer or exact string")
        rid = str(row["id"])
        require(rid in ids, f"row {i}: unknown ID {rid}")
        require(rid not in seen, f"row {i}: duplicate ID {rid}")
        seen.add(rid)
        val = row["model_output"]
        require(isinstance(val, str), f"ID {rid}: model_output must be string")
        require(len(val) <= MAX_CHARS, f"ID {rid}: response over 20000 chars")
        first_line = val.splitlines()[0].strip() if val.splitlines() else ""
        require(first_line and first_line != "ERROR", f"ID {rid}: invalid first line")
        require(not any(c in val for c in "\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029"),
                f"ID {rid}: output must be one line")
    require(seen == ids, f"Coverage incomplete: {len(seen)}/571; missing={sorted(ids-seen)[:15]}")
    return {"records": len(data), "bytes": path.stat().st_size, "unique_ids": len(seen)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("submission", type=Path)
    ap.add_argument("--source", type=Path, default=DATA)
    args = ap.parse_args()
    print(json.dumps(check(args.submission, args.source), ensure_ascii=False, indent=2))
