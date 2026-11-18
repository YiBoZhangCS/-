#!/usr/bin/env python3
"""Offline tests; no provider key or model call required."""
import json
import tempfile
import unittest
from pathlib import Path
from generate import load, select, messages, clean
from validate_submission import check


class RoleplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.profiles = load()

    def test_source_has_exactly_571_unique_ids(self):
        self.assertEqual(len(self.rows), 571)
        self.assertEqual(len(set(x["id"] for x in self.rows)), 571)
        self.assertEqual(len(set(x["role"] for x in self.rows)), 77)
        self.assertTrue(all(x["role"] in self.profiles for x in self.rows))

    def test_deterministic_role_stratified_subset(self):
        a = select(self.rows, 40, 20261118)
        b = select(self.rows, 40, 20261118)
        self.assertEqual([x["id"] for x in a], [x["id"] for x in b])
        self.assertEqual(len(set(x["role"] for x in a)), 40)
        self.assertEqual(len(select(self.rows, 571, 20261118)), 571)

    def test_prompt_includes_full_context_and_profile(self):
        row = self.rows[0]
        ms = messages(row, self.profiles[row["role"]], "structured")
        self.assertIn(row["context"], ms[1]["content"])
        self.assertIn(row["role"], ms[1]["content"])

    def test_output_cleaning(self):
        self.assertEqual(clean("佟湘玉：你说什么？\n额外的内容", "佟湘玉"), "你说什么？")
        with self.assertRaises(ValueError):
            clean("\n不是首行", "佟湘玉")
        with self.assertRaises(ValueError):
            clean("ERROR", "佟湘玉")

    def test_full_submission_validation(self):
        data = [{"id": x["id"], "model_output": "这是用于格式测试的占位台词。"}
                for x in self.rows]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "submission.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(check(path)["records"], 571)
            data.pop()
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                check(path)


if __name__ == "__main__":
    unittest.main()
