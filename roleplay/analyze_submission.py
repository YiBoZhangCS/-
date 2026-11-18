"""Strict format validation plus transparent heuristic flags, not quality scores."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import statistics

from validate_submission import check


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("submission", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    validation = check(args.submission)
    rows = json.loads(args.submission.read_text(encoding="utf-8"))
    lengths = [len(r["model_output"]) for r in rows]
    flags = []
    duplicates = Counter(r["model_output"] for r in rows)
    for row in rows:
        text = row["model_output"]
        reasons = []
        if not re.search(r"[\u3400-\u9fff]", text):
            reasons.append("no_chinese_character")
        if re.search(r"作为.{0,6}(AI|人工智能)|无法扮演|不能扮演|语言模型|不能继续这段", text, re.I):
            reasons.append("possible_meta_or_refusal")
        without_actions = text
        while True:
            value = re.sub(r"（[^（）]*）|\([^()]*\)", "", without_actions)
            if value == without_actions:
                break
            without_actions = value
        if not re.sub(r"[\s，。！？、；：…—,.!?;:\"“”‘’'-]", "", without_actions):
            reasons.append("possible_action_only")
        if len(text) > 200:
            reasons.append("over_200_chars_review")
        if reasons:
            flags.append({"id": row["id"], "reasons": reasons, "model_output": text})
    report = {"validation": validation, "sha256": hashlib.sha256(args.submission.read_bytes()).hexdigest(),
              "length_chars": {"min": min(lengths), "median": statistics.median(lengths),
                               "mean": statistics.mean(lengths), "max": max(lengths)},
              "histogram": {label: sum(lo <= n <= hi for n in lengths) for label, lo, hi in
                            [("1-19", 1, 19), ("20-49", 20, 49), ("50-99", 50, 99),
                             ("100-199", 100, 199), ("200+", 200, 20000)]},
              "heuristic_flags": flags,
              "duplicate_answer_groups": [{"answer": text, "count": n} for text, n in duplicates.items() if n > 1],
              "note": "Heuristic flags identify review candidates, not proven errors or CharacterRM scores."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"validation": validation, "length_chars": report["length_chars"],
                      "heuristic_flags": flags, "duplicate_groups": len(report["duplicate_answer_groups"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
