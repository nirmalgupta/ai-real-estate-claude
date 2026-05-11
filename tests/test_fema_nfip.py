"""Logic tests for OpenFEMA NFIP claims fetcher (no network)."""
import unittest
from datetime import datetime, timezone

from pipeline.fetch.fema_nfip import _claim_total, _cutoff_iso, _summarize


class TestClaimTotal(unittest.TestCase):
    def test_sums_all_three_payouts(self):
        c = {
            "amountPaidOnBuildingClaim": 12000,
            "amountPaidOnContentsClaim": 3000,
            "amountPaidOnIncreasedCostOfComplianceClaim": 500,
        }
        self.assertEqual(_claim_total(c), 15500.0)

    def test_treats_missing_as_zero(self):
        c = {"amountPaidOnBuildingClaim": 5000}
        self.assertEqual(_claim_total(c), 5000.0)

    def test_ignores_non_numeric(self):
        c = {"amountPaidOnBuildingClaim": "n/a"}
        self.assertEqual(_claim_total(c), 0.0)

    def test_empty_claim(self):
        self.assertEqual(_claim_total({}), 0.0)


class TestSummarize(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(
            _summarize([]),
            {"count": 0, "total": 0.0, "max": 0.0, "median": 0.0},
        )

    def test_known_values(self):
        claims = [
            {"amountPaidOnBuildingClaim": 10000},
            {"amountPaidOnBuildingClaim": 30000, "amountPaidOnContentsClaim": 5000},
            {"amountPaidOnBuildingClaim": 8000},
        ]
        s = _summarize(claims)
        self.assertEqual(s["count"], 3)
        self.assertEqual(s["total"], 53000.0)
        self.assertEqual(s["max"], 35000.0)
        self.assertEqual(s["median"], 10000.0)


class TestCutoff(unittest.TestCase):
    def test_ten_year_window(self):
        fixed = datetime(2026, 5, 11, tzinfo=timezone.utc)
        self.assertEqual(_cutoff_iso(10, now=fixed), "2016-05-13")

    def test_one_year_window(self):
        fixed = datetime(2026, 5, 11, tzinfo=timezone.utc)
        self.assertEqual(_cutoff_iso(1, now=fixed), "2025-05-11")


if __name__ == "__main__":
    unittest.main()
