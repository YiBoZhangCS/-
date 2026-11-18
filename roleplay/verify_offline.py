"""Reproducible offline acceptance checks; records actual command results."""
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform
import re
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    commands = [
        [sys.executable, "-m", "unittest", "discover", "-s", "roleplay", "-p", "test_*.py", "-v"],
        [sys.executable, "-O", "-m", "unittest", "discover", "-s", "roleplay", "-p", "test_*.py", "-v"],
        [sys.executable, "roleplay/audit_data.py"],
    ]
    results = []
    for cmd in commands:
        result = subprocess.run(cmd, cwd=root, text=True, capture_output=True)
        output = result.stdout + result.stderr
        print(output, end="")
        count = re.search(r"Ran (\d+) tests", output)
        results.append({"command": cmd, "returncode": result.returncode,
                        "test_count": int(count.group(1)) if count else None,
                        "output": output})
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "python": platform.python_version(),
              "packages": {name: version(name) for name in ("openai", "httpx")},
              "all_passed": all(r["returncode"] == 0 for r in results),
              "live_inference_requests": 0, "results": results}
    path = root / "roleplay/audit/offline_verification.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not report["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
