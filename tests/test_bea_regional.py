"""Logic tests for BEA Regional fetcher (no network)."""
import unittest

from pipeline.fetch.bea_regional import _cagr, _pick_series, _to_float


class TestToFloat(unittest.TestCase):
    def test_numeric_string(self):
        self.assertEqual(_to_float("82500"), 82500.0)

    def test_comma_separated(self):
        self.assertEqual(_to_float("82,500"), 82500.0)

    def test_blank_and_none(self):
        self.assertIsNone(_to_float(""))
        self.assertIsNone(_to_float(None))

    def test_na_marker(self):
        # BEA uses (NA), (D), (L) for suppressed/withheld
        self.assertIsNone(_to_float("(NA)"))
        self.assertIsNone(_to_float("(D)"))


class TestCagr(unittest.TestCase):
    def test_known_doubling(self):
        # 1.0 → 2.0 over 7 years ≈ 10.4% CAGR
        r = _cagr(1.0, 2.0, 7)
        self.assertAlmostEqual(r, 0.1041, places=3)

    def test_zero_start_returns_none(self):
        self.assertIsNone(_cagr(0, 100, 5))

    def test_zero_years_returns_none(self):
        self.assertIsNone(_cagr(100, 200, 0))


class TestPickSeries(unittest.TestCase):
    def test_sorts_and_filters(self):
        rows = [
            {"TimePeriod": "2022", "DataValue": "82,500"},
            {"TimePeriod": "2018", "DataValue": "60,000"},
            {"TimePeriod": "2019", "DataValue": "(NA)"},
            {"TimePeriod": "2020", "DataValue": "65,000"},
        ]
        series = _pick_series(rows)
        self.assertEqual(series[0], (2018, 60000.0))
        self.assertEqual(series[-1], (2022, 82500.0))
        # NA dropped
        years = [y for y, _ in series]
        self.assertNotIn(2019, years)

    def test_empty_rows(self):
        self.assertEqual(_pick_series([]), [])


if __name__ == "__main__":
    unittest.main()
