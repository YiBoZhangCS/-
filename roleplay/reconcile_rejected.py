"""Release two 400 reservations only with unchanged adjacent model billing counters."""
import json
from generate import OUT_DIR, ROOT, save
from safety import Ledger


def record(path, index):
    return json.loads((OUT_DIR / path).read_text(encoding="utf-8").splitlines()[index])


def main():
    cases = [
        ("smoke_glm_no_thinking_v1", "smoke_glm_v1/attempts.jsonl", "smoke_glm_2048_v1/attempts.jsonl"),
        ("smoke_glm_no_thinking_v2", "cmp_glm_structured40_v1/batches.jsonl", "cmp_glm_low_structured40_v1/batches.jsonl"),
    ]
    ledger = Ledger(OUT_DIR / "budget.sqlite3")
    evidence = []
    try:
        for run, previous, following in cases:
            before = record(previous, -1)["billing_evidence"]
            after = record(following, 0)["billing_evidence"]
            error = record(run + "/errors.jsonl", 0)
            if (error.get("http_status") != 400 or before["requests_after"] != after["requests_before"]
                    or before["cost_after_usd"] != after["cost_before_usd"]):
                raise SystemExit("No zero-charge proof; keep reservation")
            ident = error["charge_id"]
            amount, state = ledger.db.execute("SELECT amount,state FROM charges WHERE id=?", (ident,)).fetchone()
            if state == "reserved_unknown":
                ledger.settle(ident, 0)
            elif amount != 0:
                raise SystemExit("Ledger mismatch")
            evidence.append({"run_id": run, "charge_id": ident, "http_status": 400, "actual_usd": 0,
                             "previous_source": previous, "following_source": following,
                             "previous_counter": before, "following_counter": after})
    finally:
        ledger.close()
    save(ROOT / "roleplay/audit/rejected_request_reconciliation.json", evidence)
    print("Two rejected requests reconciled: no model-count or actual_cost increase; reservations released")


if __name__ == "__main__":
    main()
