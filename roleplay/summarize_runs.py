"""Publish safe configs, cleaned outputs and real ledger totals (not fabricated scores)."""
import json
from pathlib import Path
import sqlite3
import statistics
from collections import Counter

from generate import OUT_DIR, ROOT, save
from validate_submission import check


def read_records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def main():
    public = ROOT / "roleplay/results"
    public.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(OUT_DIR / "budget.sqlite3") as db:
        ledger = db.execute("SELECT id,run,amount,state FROM charges ORDER BY id").fetchall()
    totals = {"provider_billed_usd": sum(x[2] for x in ledger if x[3] == "usage_estimate"),
              "unknown_reserved_usd": sum(x[2] for x in ledger if x[3] == "reserved_unknown")}
    totals["budget_remaining_after_reservations_usd"] = 100 - sum(x[2] for x in ledger)
    runs = []
    for folder in sorted(OUT_DIR.iterdir()):
        if not folder.is_dir() or not (folder / "manifest.json").exists():
            continue
        config = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        records = read_records(folder / "responses.jsonl")
        attempts = read_records(folder / "attempts.jsonl")
        errors = read_records(folder / "errors.jsonl")
        lengths = [len(r["model_output"]) for r in records]
        run_ledger = [x for x in ledger if x[1] == folder.name]
        item = {"run_id": folder.name, "model": config["model"], "strategy": config["strategy"],
                "requested_samples": config["limit"], "completed_samples": len(records),
                "successful_http_responses": len(attempts), "logged_errors": len(errors),
                "input_tokens": sum(r["input_tokens"] for r in attempts),
                "output_tokens": sum(r["output_tokens"] for r in attempts),
                "delivered_input_tokens": sum(r["input_tokens"] for r in records),
                "delivered_output_tokens": sum(r["output_tokens"] for r in records),
                "model_distribution": dict(Counter(r.get("model_used", config["model"]) for r in records)),
                "provider_billed_usd": sum(x[2] for x in run_ledger if x[3] == "usage_estimate"),
                "unknown_reserved_usd": sum(x[2] for x in run_ledger if x[3] == "reserved_unknown"),
                "raw_empty_count": sum(not r.get("raw_output") for r in attempts),
                "incomplete_count": sum(not r.get("complete", True) for r in attempts),
                "multiline_raw_count": sum("\n" in (r.get("raw_output") or "") for r in attempts),
                "unique_outputs": len({r["model_output"] for r in records}),
                "oj_scores": None, "local_characterrm_scores": None}
        success_keys = {(r["id"], r["charge_id"], r.get("model_used", config["model"])) for r in attempts}
        item["inference_requests"] = len(attempts) + sum(
            (r["id"], r["charge_id"], r.get("model_used", config["model"])) not in success_keys for r in errors)
        item["imported_cost_attribution_usd"] = sum(r["estimated_usd"] for r in records if r.get("source_run"))
        item["submission_attributed_usd"] = item["provider_billed_usd"] + item["imported_cost_attribution_usd"]
        if lengths:
            item["length_chars"] = {"min": min(lengths), "median": statistics.median(lengths),
                                    "mean": statistics.mean(lengths), "max": max(lengths)}
            item["length_histogram"] = {label: sum(lo <= x <= hi for x in lengths) for label, lo, hi in
                                        [("1-19", 1, 19), ("20-49", 20, 49), ("50-99", 50, 99),
                                         ("100-199", 100, 199), ("200+", 200, 20000)]}
            item["mean_request_latency_s"] = statistics.mean(r["latency_s"] for r in records)
            item["format_anomaly_ids"] = [r["id"] for r in records if not isinstance(r["model_output"], str)
                                          or "\n" in r["model_output"] or not r["model_output"].strip()]
        if (folder / "submission.json").exists():
            if (folder / "assembly_manifest.json").exists():
                item["submission_alias"] = json.loads((folder / "assembly_manifest.json").read_text(encoding="utf-8"))
            else:
                item["submission_validation"] = check(folder / "submission.json")
        runs.append(item)
        dest = public / folder.name
        dest.mkdir(parents=True, exist_ok=True)
        save(dest / "manifest.json", config)
        save(dest / "outputs.json", [{"id": r["id"], "model_output": r["model_output"]} for r in records])
        save(dest / "provenance.json", [{"id": r["id"], "model_used": r.get("model_used", config["model"]),
             "source_run": r.get("source_run", folder.name), "charge_id": r["charge_id"],
             "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"]} for r in records])
        save(dest / "billing_batches.json", [{"charge_id": r["charge_id"], "ids": r["ids"],
             "actual_usd": r["actual_usd"]} for r in read_records(folder / "batches.jsonl")])
    totals["inference_requests"] = sum(r["inference_requests"] for r in runs)
    totals["responses_with_usage"] = sum(r["successful_http_responses"] for r in runs)
    totals["input_tokens_all_experiments"] = sum(r["input_tokens"] for r in runs)
    totals["output_tokens_all_experiments"] = sum(r["output_tokens"] for r in runs)
    save(public / "billing_ledger.json", [{"charge_id": x[0], "run_id": x[1], "usd": x[2], "state": x[3]} for x in ledger])
    save(public / "experiment_summary.json", {"totals": totals, "runs": runs,
         "cost_note": "Batch totals are provider actual_cost deltas; per-row allocations are approximate. Pending reservations are not claimed as actual spend."})
    print(json.dumps({"totals": totals, "runs": [{k: r[k] for k in ("run_id", "completed_samples", "provider_billed_usd", "unknown_reserved_usd")} for r in runs]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
