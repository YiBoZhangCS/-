"""Reconcile a stopped batch using the next run's recorded model-counter baseline."""
import argparse
import json
from pathlib import Path

from generate import OUT_DIR, append_record, save
from safety import Ledger


def records(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stopped_run")
    parser.add_argument("successor_run")
    args = parser.parse_args()
    old, new = OUT_DIR / args.stopped_run, OUT_DIR / args.successor_run
    configs = [json.loads((p / "manifest.json").read_text()) for p in (old, new)]
    if configs[0]["model"] != configs[1]["model"]:
        raise SystemExit("Primary models differ")
    old_batches = records(old / "batches.jsonl")
    next_batch = records(new / "batches.jsonl")[0]
    baseline = old_batches[-1]["billing_evidence"]
    next_baseline = next_batch["billing_evidence"]
    next_baseline = next_baseline.get("primary", next_baseline)
    charged = {x["charge_id"] for x in old_batches}
    pending_receipts = [r for r in records(old / "receipts.jsonl") if r["charge_id"] not in charged]
    charge_ids = {r["charge_id"] for r in pending_receipts}
    if len(charge_ids) != 1 or not pending_receipts:
        raise SystemExit("Expected exactly one stopped batch with durable successful receipts")
    ident = next(iter(charge_ids))
    delta_count = next_baseline["requests_before"] - baseline["requests_after"]
    delta_cost = next_baseline["cost_before_usd"] - baseline["cost_after_usd"]
    if delta_count != len(pending_receipts) or delta_cost < 0:
        raise SystemExit("Model counters do not match durable receipts; keep reservation")
    evidence = {"charge_id": ident, "successful_receipts": len(pending_receipts),
                "actual_usd": delta_cost, "old_batch_end": baseline, "next_run_begin": next_baseline,
                "note": "Counter increase exactly matches durable receipts; no inference call is made by reconciliation."}
    save(old / "billing_reconciliation.json", evidence)
    ledger = Ledger(OUT_DIR / "budget.sqlite3")
    try:
        row = ledger.db.execute("SELECT amount,state FROM charges WHERE id=?", (ident,)).fetchone()
        if row[1] == "reserved_unknown":
            ledger.settle(ident, delta_cost)
        elif abs(row[0] - delta_cost) > 1e-9:
            raise SystemExit("Ledger does not match reconciliation")
    finally:
        ledger.close()
    existing = {(r["charge_id"], r["id"]) for r in records(old / "attempts.jsonl")}
    for receipt in pending_receipts:
        if (ident, receipt["id"]) in existing:
            continue
        response = receipt["response"]
        usage, choice = response["usage"], response["choices"][0]
        append_record(old / "attempts.jsonl", {"id": receipt["id"], "charge_id": ident,
                      "input_tokens": usage["prompt_tokens"], "output_tokens": usage["completion_tokens"],
                      "raw_output": choice["message"]["content"], "complete": choice["finish_reason"] == "stop",
                      "estimated_usd": delta_cost / len(pending_receipts), "latency_s": None,
                      "cost_source": "provider_interrupted_batch_total_equal_allocation"})
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
