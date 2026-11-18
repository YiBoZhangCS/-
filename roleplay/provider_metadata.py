"""Read model catalog and billing units only. Does not call an inference endpoint."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-insecure-http", action="store_true")
    args = parser.parse_args()
    if not args.allow_insecure_http:
        raise SystemExit("Explicit HTTP authorization required for this provider metadata check")
    key = os.getenv("ainet_key") or os.getenv("AINET_API_KEY")
    if not key:
        raise SystemExit("API key environment variable is missing")
    with httpx.Client(base_url="http://ainet-hub.com", follow_redirects=False,
                      timeout=30, headers={"Authorization": "Bearer " + key}) as client:
        models = client.get("/v1/models")
        usage = client.get("/v1/usage")
    if models.status_code != 200 or usage.status_code != 200:
        raise SystemExit(f"Metadata status: models={models.status_code}, usage={usage.status_code}")
    catalog, billing = models.json(), usage.json()
    result = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": "http://ainet-hub.com/v1", "transport": "HTTP",
        "http_authorization": "Explicit user instruction in this chat on 2026-11-18",
        "model_endpoint_status": models.status_code, "usage_endpoint_status": usage.status_code,
        "models": [{k: row.get(k) for k in ("id", "display_name", "owned_by", "type")}
                   for row in catalog.get("data", [])],
        "billing_unit": billing.get("unit"),
        "inference_requests_by_this_script": 0,
        "verified_prices": [], "verified_inference_interfaces": [],
        "note": "Catalog IDs are provider aliases; backing model identity is not independently verified. No rates are present in these metadata responses.",
    }
    path = Path(__file__).parent / "audit" / "provider_catalog.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(result['models'])} catalog IDs; billing unit={result['billing_unit']}; inference requests=0")


if __name__ == "__main__":
    try:
        main()
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise SystemExit(f"Metadata check failed: {type(exc).__name__}") from None
