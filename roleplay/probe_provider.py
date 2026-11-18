"""Public, credential-free connectivity checks. NEVER reads any API key."""
import concurrent.futures
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import httpx


def probe(target):
    url, trust_env = target
    result = {"url": url, "route": "environment_proxy" if trust_env else "direct"}
    try:
        with httpx.Client(timeout=8, trust_env=trust_env, follow_redirects=False) as client:
            response = client.get(url)
            result["http_status"] = response.status_code
    except httpx.HTTPError as exc:
        # Exception strings can include proxy credentials; store only their class.
        result["error_type"] = type(exc).__name__
    return result


def main():
    targets = [(f"https://{host}", route) for host in
               ("ainet-hub.com", "www.ainet-hub.com", "api.ainet-hub.com")
               for route in (True, False)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(probe, targets))
    public = {"source": "http://ainet-hub.com", "trusted_transport": False}
    try:
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            response = client.get(public["source"])
            public["http_status"] = response.status_code
            match = re.search(r"window\.__APP_CONFIG__=(.*?);</script>", response.text)
            if match:
                config = json.loads(match.group(1))
                public["settings"] = {name: config.get(name) for name in
                                      ("api_base_url", "doc_url", "custom_endpoints", "model_plaza_enabled")}
    except (httpx.HTTPError, ValueError) as exc:
        public["error_type"] = type(exc).__name__
    result = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "credentials_sent": False, "inference_requests": 0,
              "https_probes": results, "public_http_metadata": public,
              "verified_api_base_url": None, "verified_model_ids": [],
              "verified_prices": [],
              "note": "Connectivity or public HTML alone cannot verify API ownership, pricing, or compatibility."}
    path = Path(__file__).parent / "audit" / "provider_verification.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
