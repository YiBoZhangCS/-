"""Fail-closed local spending reservations. Unknown charges stay reserved."""
import math
import sqlite3
import time
from urllib.parse import urlsplit


def validate_options(args):
    url = urlsplit(args.base_url)
    permitted_scheme = url.scheme == "https" or (
        getattr(args, "allow_insecure_http", False) and url.scheme == "http"
        and url.hostname == "ainet-hub.com" and url.port in (None, 80))
    if (not permitted_scheme or not url.hostname or url.username or url.password
            or url.query or url.fragment):
        raise ValueError("Use HTTPS, or explicitly authorize HTTP for ainet-hub.com only")
    for value in (args.budget, args.global_budget):
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Prices and budgets must be finite and positive")
    if getattr(args, "billing_mode", "rates") == "rates":
        if any(not math.isfinite(v) or v <= 0 for v in (args.price_in, args.price_out)):
            raise ValueError("Verified rates must be positive")
    elif not math.isfinite(args.request_reserve) or args.request_reserve <= 0:
        raise ValueError("Per-request USD reservation must be positive")
    if args.global_budget > 100 or args.max_output_tokens <= 0:
        raise ValueError("Global budget cannot exceed USD 100; token cap must be positive")
    if args.temperature is not None and not math.isfinite(args.temperature):
        raise ValueError("Temperature must be finite")
    if args.run_id in (".", ".."):
        raise ValueError("Invalid run directory")


class Ledger:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS charges "
                        "(id INTEGER PRIMARY KEY, run TEXT, amount REAL, state TEXT)")
        self.db.commit()

    def reserve(self, run, amount, run_cap, global_cap):
        if any(not math.isfinite(v) or v <= 0 for v in (amount, run_cap, global_cap)):
            raise ValueError("Invalid reservation")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            total = self.db.execute("SELECT coalesce(sum(amount),0) FROM charges").fetchone()[0]
            subtotal = self.db.execute("SELECT coalesce(sum(amount),0) FROM charges WHERE run=?",
                                       (run,)).fetchone()[0]
            if total + amount > min(100, global_cap) or subtotal + amount > run_cap:
                raise ValueError("Budget exhausted including pending/unknown charges")
            ident = self.db.execute("INSERT INTO charges(run,amount,state) VALUES(?,?,?)",
                                    (run, amount, "reserved_unknown")).lastrowid
            self.db.commit()
            return ident
        except BaseException:
            self.db.rollback()
            raise

    def settle(self, ident, amount):
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("Invalid charge")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT amount,state FROM charges WHERE id=?", (ident,)).fetchone()
            if row is None or row[1] != "reserved_unknown":
                raise ValueError("Unknown or already settled reservation")
            old = row[0]
            self.db.execute("UPDATE charges SET amount=?,state=? WHERE id=?",
                            (amount, "usage_estimate", ident))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        if amount > old:
            raise ValueError("Usage exceeded reservation; stop and reconcile provider billing")

    def close(self):
        self.db.close()


class ProviderMeter:
    """Use this gateway's per-model actual_cost deltas instead of inventing rates."""
    def __init__(self, client, base_url, key):
        self.client = client
        self.url = base_url.rstrip("/") + "/usage"
        self.headers = {"Authorization": "Bearer " + key}

    def snapshot(self, model):
        response = self.client.get(self.url, headers=self.headers)
        if response.status_code != 200:
            raise ValueError("Provider billing metadata unavailable")
        data = response.json()
        if data.get("unit") != "USD":
            raise ValueError("Provider billing unit is not USD")
        for row in data.get("model_stats", []):
            if row.get("model") == model:
                cost = float(row["actual_cost"])
                count = row["requests"]
                if not math.isfinite(cost) or cost < 0 or type(count) is not int or count < 0:
                    raise ValueError("Invalid provider billing counters")
                return count, cost
        return 0, 0.0

    def charge_since(self, model, before, expected=1):
        for attempt in range(5):
            count, cost = self.snapshot(model)
            if count > before[0] + expected or cost < before[1]:
                raise ValueError("Concurrent usage or decreasing counter; reconcile billing")
            if count == before[0] + expected:
                if cost < before[1]:
                    raise ValueError("Concurrent usage or decreasing counter; reconcile billing")
                return cost - before[1], {"requests_before": before[0], "requests_after": count,
                                          "cost_before_usd": before[1], "cost_after_usd": cost}
            if attempt < 4:
                time.sleep(1)
        raise ValueError("Provider billing has not updated; keep reservation and stop")
