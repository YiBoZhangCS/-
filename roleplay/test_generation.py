"""Offline end-to-end tests with a fake SDK; no requests and no real key."""
import contextlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

import httpx
import generate
from openai import BadRequestError, APIConnectionError, RateLimitError, InternalServerError


def completion(text="（点头）这件事还需仔细想想。", tin=100, tout=20, finish="stop"):
    return NS(choices=[NS(message=NS(content=text), finish_reason=finish)],
              usage=NS(prompt_tokens=tin, completion_tokens=tout),
              model_dump=lambda **kw: {"choices": [{"message": {"content": text}, "finish_reason": finish}],
                                       "usage": {"prompt_tokens": tin, "completion_tokens": tout}})


class GenerationTests(unittest.TestCase):
    def test_declared_warm_start_reuses_equivalent_outputs_without_new_charge(self):
        with tempfile.TemporaryDirectory() as folder:
            _, _, error = self.invoke(folder, [completion()])
            self.assertIsNone(error)
            create, _, error = self.invoke(folder, [], ["--run-id", "followup", "--warm-start", "smoke"])
            self.assertIsNone(error)
            self.assertEqual(create.call_count, 0)
            records = (Path(folder) / "followup/responses.jsonl").read_text()
            self.assertEqual(json.loads(records)["source_run"], "smoke")
            self.assertEqual(len(self.charges(folder)), 1)

    def test_provider_error_redaction_before_truncation(self):
        key = "OFFLINE_TEST_SECRET_LONG_VALUE"
        exc = NS(body={"message": "x" * 1990 + key + " Bearer abcdef sk-demo-secret"})
        with patch.dict(os.environ, {"ainet_key": key}):
            text = generate.safe_error_detail(exc)
        self.assertNotIn(key, text)
        self.assertNotIn("abcdef", text)

    def test_explicit_provider_refusal_fallback_is_metered_and_labelled(self):
        from unittest.mock import Mock
        meter = Mock()
        meter.snapshot.return_value = (0, 0)
        meter.charge_since.side_effect = [(0, {}), (.001, {})]
        response = httpx.Response(500, request=httpx.Request("POST", "https://example.org"))
        exc = InternalServerError("blocked", response=response,
                                  body={"message": "This request was blocked by our safety systems."})
        with tempfile.TemporaryDirectory() as folder, patch.object(generate, "ProviderMeter", return_value=meter):
            extra = ["--billing-mode", "provider", "--workers", "2", "--fallback-model", "backup", "--budget", "5"]
            create, _, error = self.invoke(folder, [exc, completion()], extra)
            self.assertIsNone(error)
            self.assertEqual(create.call_count, 2)
            self.assertAlmostEqual(sum(c[0] for c in self.charges(folder)), .001)
            record = json.loads((Path(folder) / "smoke/responses.jsonl").read_text())
            self.assertEqual(record["model_used"], "backup")

    def test_parallel_batch_billing_and_resume(self):
        from unittest.mock import Mock
        meter = Mock()
        meter.snapshot.return_value = (0, 0)
        meter.charge_since.side_effect = [(.0003, {}), (.0002, {})]
        with tempfile.TemporaryDirectory() as folder, patch.object(generate, "ProviderMeter", return_value=meter):
            extra = ["--billing-mode", "provider", "--workers", "2", "--limit", "3", "--budget", "5"]
            create, _, error = self.invoke(folder, [completion()] * 3, extra)
            self.assertIsNone(error)
            self.assertEqual(create.call_count, 3)
            self.assertAlmostEqual(sum(c[0] for c in self.charges(folder)), .0005)
            self.assertEqual(len(self.charges(folder)), 2)
            records = [json.loads(x) for x in (Path(folder) / "smoke/responses.jsonl").read_text().splitlines()]
            self.assertEqual(len(records), 3)
            self.assertAlmostEqual(sum(x["estimated_usd"] for x in records), .0005)
            create, _, error = self.invoke(folder, [], extra)
            self.assertIsNone(error)
            self.assertEqual(create.call_count, 0)

    def invoke(self, folder, responses, extra=(), mode="chat"):
        client = NS(close=lambda: None)
        from unittest.mock import Mock
        create = Mock(side_effect=responses)
        client.chat = NS(completions=NS(create=create))
        client.responses = NS(create=create)
        argv = ["generate.py", "--model", "offline-fake", "--base-url", "https://example.org/v1",
                "--run-id", "smoke", "--limit", "1", "--price-in", "1", "--price-out", "2",
                "--budget", "1", "--api-mode", mode, *extra]
        stdout = io.StringIO()
        with patch.object(generate, "OUT_DIR", Path(folder)), patch.object(sys, "argv", argv), \
                patch.dict(os.environ, {"ainet_key": "OFFLINE_TEST_SECRET"}), \
                patch.object(generate, "OpenAI", return_value=client), \
                patch.object(generate.time, "sleep"), contextlib.redirect_stdout(stdout):
            try:
                generate.main()
                error = None
            except (SystemExit, ValueError) as exc:
                error = str(exc)
        return create, stdout.getvalue(), error

    def charges(self, folder):
        with sqlite3.connect(Path(folder) / "budget.sqlite3") as db:
            return db.execute("SELECT amount,state FROM charges ORDER BY id").fetchall()

    def test_success_resume_and_config_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            create, _, error = self.invoke(folder, [completion()])
            self.assertIsNone(error)
            self.assertEqual(create.call_count, 1)
            self.assertAlmostEqual(self.charges(folder)[0][0], .00014)
            raw = json.loads((Path(folder) / "smoke/attempts.jsonl").read_text())
            self.assertEqual(raw["raw_output"], completion().choices[0].message.content)
            create, _, error = self.invoke(folder, [])
            self.assertIsNone(error)
            self.assertEqual(create.call_count, 0)
            create, _, error = self.invoke(folder, [], ["--temperature", "0.5"])
            self.assertIn("Different configuration", error)
            self.assertEqual(create.call_count, 0)

    def test_dry_run_makes_no_request_or_charge(self):
        with tempfile.TemporaryDirectory() as folder:
            create, output, error = self.invoke(folder, [], ["--dry-run"])
            self.assertIsNone(error)
            self.assertEqual(create.call_count, 0)
            self.assertIn("DRY RUN", output)
            self.assertFalse((Path(folder) / "budget.sqlite3").exists())

    def test_insecure_endpoint_fails_before_request(self):
        with tempfile.TemporaryDirectory() as folder:
            create, _, error = self.invoke(folder, [], ["--base-url", "http://example.org/v1"])
            self.assertIsNotNone(error)
            self.assertEqual(create.call_count, 0)
            self.assertFalse((Path(folder) / "budget.sqlite3").exists())

    def test_400_not_retried_or_logged(self):
        with tempfile.TemporaryDirectory() as folder:
            response = httpx.Response(400, request=httpx.Request("POST", "https://example.org/v1"))
            exc = BadRequestError("OFFLINE_TEST_SECRET", response=response, body=None)
            create, output, error = self.invoke(folder, [exc])
            self.assertEqual(create.call_count, 1)
            self.assertIsNotNone(error)
            self.assertNotIn("OFFLINE_TEST_SECRET", output + error)
            self.assertEqual(self.charges(folder)[0][1], "reserved_unknown")

    def test_timeout_and_429_keep_reservations(self):
        with tempfile.TemporaryDirectory() as folder:
            req = httpx.Request("POST", "https://example.org/v1")
            timeout = APIConnectionError(request=req)
            limited = RateLimitError("limited", response=httpx.Response(429, request=req), body=None)
            create, _, error = self.invoke(folder, [timeout, limited, completion()])
            self.assertIsNone(error)
            self.assertEqual(create.call_count, 3)
            self.assertEqual([x[1] for x in self.charges(folder)],
                             ["reserved_unknown", "reserved_unknown", "usage_estimate"])

    def test_billable_invalid_output_and_incomplete_not_retried(self):
        for fake in (completion("ERROR"), completion(finish="length"), completion(tin=0, tout=0)):
            with self.subTest(fake=fake), tempfile.TemporaryDirectory() as folder:
                create, _, error = self.invoke(folder, [fake])
                self.assertEqual(create.call_count, 1)
                self.assertIsNotNone(error)
                self.assertTrue((Path(folder) / "smoke/attempts.jsonl").exists())
                self.assertFalse((Path(folder) / "smoke/responses.jsonl").exists())
                self.assertGreater(self.charges(folder)[0][0], 0)

    def test_responses_mode_parameters(self):
        with tempfile.TemporaryDirectory() as folder:
            fake = NS(output_text="这话我记下了。", status="completed",
                      usage=NS(input_tokens=100, output_tokens=20))
            create, _, error = self.invoke(folder, [fake],
                                          ["--temperature", "0.5", "--reasoning-effort", "low"],
                                          mode="responses")
            self.assertIsNone(error)
            self.assertEqual(create.call_args.kwargs["reasoning"], {"effort": "low"})
            self.assertEqual(create.call_args.kwargs["temperature"], .5)
            self.assertEqual(create.call_args.kwargs["max_output_tokens"], 320)

    def test_budget_stops_before_second_request(self):
        with tempfile.TemporaryDirectory() as folder:
            rows, profiles = generate.load()
            item = generate.select(rows, 1, 20261118)[0]
            msg = generate.messages(item, profiles[item["role"]], "structured")
            reservation = (1024 + sum(len(x["content"].encode("utf-8")) for x in msg) + 640) / 1e6
            create, _, error = self.invoke(folder, [APIConnectionError(
                request=httpx.Request("POST", "https://example.org"))] * 3,
                ["--budget", str(reservation * 1.5)])
            self.assertIsNotNone(error)
            self.assertEqual(create.call_count, 1)
