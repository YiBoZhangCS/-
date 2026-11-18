"""Record read-only publication metadata and official-code revision evidence."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re

import httpx

URLS = [
    "https://aclanthology.org/2024.acl-long.638/",
    "https://arxiv.org/abs/2509.00482",
    "https://papers.neurips.cc/paper_files/paper/2025/hash/15294ba2dcfb4521274f7aa1c26f4dd4-Abstract-Conference.html",
    "https://api.github.com/repos/morecry/CharacterEval/commits/main",
]


def fetch(url):
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        response = client.get(url)
    result = {"url": url, "http_status": response.status_code,
              "sha256_response": hashlib.sha256(response.content).hexdigest()}
    if "api.github.com" in url and response.status_code == 200:
        result["commit_sha"] = response.json()["sha"]
    else:
        title = re.search(r"<title[^>]*>(.*?)</title>", response.text, re.S | re.I)
        result["title"] = html.unescape(re.sub(r"\s+", " ", title.group(1)).strip()) if title else None
    return result


def main():
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(fetch, URLS))
    data = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "sources": records,
            "official_files_read": ["get_response.py", "transform_format.py", "run_char_rm.py", "compute_score.py"],
            "method_reuse": "Role profile + complete context; metric expansion and per-dimension averaging. No training or full Codified Profiles/tool agent implementation."}
    path = Path(__file__).parent / "audit/references.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
