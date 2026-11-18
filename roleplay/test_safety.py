import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from generate import clean, load, messages
from safety import Ledger, ProviderMeter, validate_options
from validate_submission import check


class SafetyTests(unittest.TestCase):
    def test_provider_meter_uses_actual_model_cost_delta(self):
        client = Mock()
        client.get.side_effect = [SimpleNamespace(status_code=200, json=lambda n=n, c=c: {
            "unit": "USD", "model_stats": [{"model": "test", "requests": n, "actual_cost": c}]})
            for n, c in [(2, .1), (3, .11)]]
        meter = ProviderMeter(client, "http://ainet-hub.com/v1", "TEST_ONLY")
        before = meter.snapshot("test")
        cost, evidence = meter.charge_since("test", before)
        self.assertAlmostEqual(cost, .01)
        self.assertEqual(evidence["requests_after"], 3)

    def test_provider_meter_stops_on_ambiguous_or_missing_updates(self):
        meter = ProviderMeter(Mock(), "http://ainet-hub.com/v1", "TEST_ONLY")
        for after in ((2, 1), (1, -.1)):
            with patch.object(meter, "snapshot", return_value=after), self.assertRaises(ValueError):
                meter.charge_since("test", (0, 0))
        with patch.object(meter, "snapshot", return_value=(0, 0)), patch("safety.time.sleep"), self.assertRaises(ValueError):
            meter.charge_since("test", (0, 0))

    def test_unknown_charge_survives_restart_and_blocks_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "budget.db"
            ledger = Ledger(path)
            ledger.reserve("smoke", .6, 1, 100)
            ledger.close()
            ledger = Ledger(path)
            with self.assertRaises(ValueError):
                ledger.reserve("smoke", .6, 1, 100)
            ledger.close()

    def test_shared_budget_and_settlement(self):
        with tempfile.TemporaryDirectory() as folder:
            a = Ledger(Path(folder) / "budget.db")
            b = Ledger(Path(folder) / "budget.db")
            ident = a.reserve("a", 60, 100, 100)
            with self.assertRaises(ValueError):
                b.reserve("b", 50, 100, 100)
            a.settle(ident, 10)
            b.reserve("b", 50, 100, 100)
            a.close()
            b.close()

    def test_hard_global_cap(self):
        with tempfile.TemporaryDirectory() as folder:
            a = Ledger(Path(folder) / "budget.db")
            with self.assertRaises(ValueError):
                a.reserve("a", 101, 999, 999)
            a.close()

    def test_charge_cannot_be_settled_twice_or_with_invalid_caps(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / "budget.db")
            ident = ledger.reserve("a", 1, 10, 100)
            ledger.settle(ident, .5)
            with self.assertRaises(ValueError):
                ledger.settle(ident, 0)
            with self.assertRaises(ValueError):
                ledger.settle(999, 0)
            for caps in ((float("nan"), 100), (10, float("inf")), (-1, 100)):
                with self.assertRaises(ValueError):
                    ledger.reserve("a", 1, *caps)
            ledger.close()

    def test_overrun_is_recorded_before_stopping(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / "budget.db")
            ident = ledger.reserve("a", .5, 1, 100)
            with self.assertRaises(ValueError):
                ledger.settle(ident, 1.1)
            with self.assertRaises(ValueError):
                ledger.reserve("a", .1, 1, 100)
            self.assertEqual(ledger.db.execute("SELECT amount FROM charges").fetchone()[0], 1.1)
            ledger.close()

    def test_url_and_numeric_options(self):
        values = dict(base_url="https://example.org/v1", price_in=1, price_out=1,
                      budget=1, global_budget=100, max_output_tokens=320, run_id="smoke", temperature=None)
        validate_options(SimpleNamespace(**values))
        for key, value in [("base_url", "http://example.org"),
                           ("base_url", "https://secret@example.org"),
                           ("base_url", "https://example.org?key=secret"),
                           ("price_in", float("nan")), ("budget", float("inf")),
                           ("global_budget", 101), ("max_output_tokens", 0),
                           ("run_id", "..")]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_options(SimpleNamespace(**(values | {key: value})))
        validate_options(SimpleNamespace(**(values | {
            "base_url": "http://ainet-hub.com/v1", "allow_insecure_http": True})))
        for url in ("http://example.org/v1", "http://ainet-hub.com:8080/v1",
                    "http://secret@ainet-hub.com/v1", "http://ainet-hub.com.evil.test/v1"):
            with self.assertRaises(ValueError):
                validate_options(SimpleNamespace(**(values | {
                    "base_url": url, "allow_insecure_http": True})))

    def test_all_prompts_preserve_entire_source(self):
        rows, cards = load()
        for row in rows:
            for strategy in ("baseline", "structured"):
                text = messages(row, cards[row["role"]], strategy)[1]["content"]
                self.assertIn(row["context"], text)
                self.assertIn(json.dumps(cards[row["role"]], ensure_ascii=False), text)

    def test_no_profile_ablation_preserves_context_but_omits_profile(self):
        rows, cards = load()
        for row in rows:
            text = messages(row, cards[row["role"]], "no_profile")[1]["content"]
            self.assertIn(row["context"], text)
            self.assertIn(row["role"], text)
            self.assertNotIn("角色画像：", text)

    def test_line_boundaries_and_types(self):
        for sep in ("\n", "\r", "\r\n", "\u2028", "\u2029", "\x85"):
            self.assertEqual(clean("甲" + sep + "乙", "角色"), "甲")
        for value in (None, 123, {}, "", "\n台词", "角色：ERROR"):
            with self.assertRaises(ValueError):
                clean(value, "角色")

    def test_invalid_submission_variants(self):
        rows, _ = load()
        original = [{"id": r["id"], "model_output": "仅用于离线格式校验"} for r in rows]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "submission.json"
            for change in ({"id": True}, {"id": float(rows[0]["id"])},
                           {"id": "0" + str(rows[0]["id"])}, {"id": rows[1]["id"]},
                           {"model_output": None}, {"model_output": "ERROR"},
                           {"model_output": "甲\u2028乙"}, {"model_output": "甲" * 20001}):
                data = [dict(r) for r in original]
                data[0].update(change)
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                with self.subTest(change=list(change)), self.assertRaises(ValueError):
                    check(path)
