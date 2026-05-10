"""Pure-logic tests for NOAA SPC helpers (no network)."""
import re
import unittest

from pipeline.fetch.noaa_spc import _date_range_clause


class TestDateRange(unittest.TestCase):
    def test_clause_shape(self):
        c = _date_range_clause(10, "BEGIN_DATE")
        self.assertIn("BEGIN_DATE >=", c)
        self.assertIn("BEGIN_DATE <=", c)
        self.assertIn("DATE '", c)
        # Two literal yyyy-mm-dd dates expected.
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", c)
        self.assertEqual(len(dates), 2)
        # End >= start lexicographically (works for ISO dates).
        self.assertLessEqual(dates[0], dates[1])

    def test_lookback_window_is_n_years(self):
        clause = _date_range_clause(10, "BEGIN_DATE")
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", clause)
        start_year = int(dates[0][:4])
        end_year = int(dates[1][:4])
        self.assertEqual(end_year - start_year, 10)


if __name__ == "__main__":
    unittest.main()
