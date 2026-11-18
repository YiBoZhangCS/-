"""Read every input record and write reproducible, non-generative data statistics."""
import hashlib
import json
import statistics
from collections import Counter
from generate import DATA_DIR, load, messages, save
from validate_submission import require


def main():
    rows, cards = load()
    metrics = json.loads((DATA_DIR / "id2metric.jsonl").read_text(encoding="utf-8"))
    require(isinstance(metrics, dict), "Metric mapping must be an object")
    for row in rows:
        require(type(row["id"]) is int, "Source ID must be integer")
        require(all(isinstance(row[k], str) and row[k].strip() for k in ("role", "novel_name", "context")), "Invalid source text")
        require(isinstance(cards[row["role"]], dict), "Profile must be an object")
        require(row["context"] in messages(row, cards[row["role"]], "structured")[1]["content"], "Context lost")
    for values in metrics.values():
        require(isinstance(values, list), "Metric values must be a list")
        require(all(isinstance(pair, list) and len(pair) == 2 and
                    all(isinstance(x, str) and x for x in pair) for pair in values),
                "Each metric must have an English and Chinese label")
    def stats(values):
        values = sorted(values)
        return {"min": min(values), "median": statistics.median(values),
                "p90_nearest_rank": values[(9 * len(values) + 9) // 10 - 1], "max": max(values)}
    result = {
        "records": len(rows), "unique_ids": len({r["id"] for r in rows}),
        "roles": len({r["role"] for r in rows}), "novels": len({r["novel_name"] for r in rows}),
        "profile_count": len(cards), "metric_id_count": len(metrics),
        "missing_metric_ids": [r["id"] for r in rows if str(r["id"]) not in metrics],
        "extra_metric_ids": sorted(set(metrics) - {str(r["id"]) for r in rows}),
        "metric_values": dict(Counter(pair[0] for values in metrics.values() for pair in values)),
        "context_chars": stats([len(r["context"]) for r in rows]),
        "profile_json_chars_per_sample": stats([len(json.dumps(cards[r["role"]], ensure_ascii=False)) for r in rows]),
        "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(DATA_DIR.iterdir()) if p.is_file()},
    }
    path = DATA_DIR.parent / "roleplay" / "audit" / "data_stats.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    save(path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
