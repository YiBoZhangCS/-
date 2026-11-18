"""Export a validated immutable final run to the course-required delivery filename."""
import hashlib
import json
from pathlib import Path
import shutil

from generate import ROOT, OUT_DIR, save
from validate_submission import check


def main():
    source = OUT_DIR / "final_v2/submission.json"
    validation = check(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    destinations = [OUT_DIR / "final_v1/submission.json", ROOT / "roleplay/results/submission.json"]
    for target in destinations:
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise SystemExit("Different existing artifact; will not overwrite: " + str(target))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        check(target)
    manifest = {"source_run": "final_v2", "source_file": str(source.relative_to(ROOT)),
                "destination_file": "roleplay/runs/final_v1/submission.json", "sha256": digest,
                "note": "final_v1 inference was interrupted; its config/logs remain unchanged. This submission is an explicit alias of final_v2, not a claimed continuation with changed configuration."}
    save(OUT_DIR / "final_v1/assembly_manifest.json", manifest)
    save(ROOT / "roleplay/audit/submission_validation.json", {**validation, "sha256": digest,
         "primary_source": "roleplay/runs/final_v2/submission.json", "delivered_aliases": [str(p.relative_to(ROOT)) for p in destinations],
         "oj_submitted": False, "oj_scores": None})
    print(json.dumps({**validation, "sha256": digest, "oj_submitted": False}, indent=2))


if __name__ == "__main__":
    main()
