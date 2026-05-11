"""Logic tests for BLS LAUS fetcher (no network)."""
import unittest

from pipeline.fetch.bls_laus import (
    _parse_value,
    _pick_latest_and_yoy,
    _series_id,
)


class TestSeriesId(unittest.TestCase):
    def test_denton_county_tx(self):
        # Denton County TX = state 48, county 121
        self.assertEqual(_series_id("48", "121"), "LAUCN481210000000003")

    def test_dallas_county_tx(self):
        self.assertEqual(_series_id("48", "113"), "LAUCN481130000000003")


class TestParseValue(unittest.TestCase):
    def test_numeric(self):
        self.assertEqual(_parse_value("3.8"), 3.8)

    def test_blank(self):
        self.assertIsNone(_parse_value(""))
        self.assertIsNone(_parse_value(None))

    def test_garbage(self):
        self.assertIsNone(_parse_value("N/A"))


SAMPLE_BLS_DATA = [
    # Newest first — Feb 2026
    {"year": "2026", "period": "M02", "value": "3.8", "latest": "true",
     "periodName": "February"},
    {"year": "2026", "period": "M01", "value": "3.9", "latest": "false",
     "periodName": "January"},
    # Oct 2025 lapse — blank value
    {"year": "2025", "period": "M10", "value": "", "latest": "false",
     "periodName": "October"},
    {"year": "2025", "period": "M09", "value": "4.1", "latest": "false",
     "periodName": "September"},
    {"year": "2025", "period": "M02", "value": "3.5", "latest": "false",
     "periodName": "February"},  # YoY anchor
]


class TestPickLatestAndYoy(unittest.TestCase):
    def test_picks_latest_with_value(self):
        latest, _ = _pick_latest_and_yoy(SAMPLE_BLS_DATA)
        self.assertEqual(latest["year"], "2026")
        self.assertEqual(latest["period"], "M02")
        self.assertEqual(latest["value"], "3.8")

    def test_yoy_matches_same_month_year_earlier(self):
        _, yoy = _pick_latest_and_yoy(SAMPLE_BLS_DATA)
        self.assertEqual(yoy["year"], "2025")
        self.assertEqual(yoy["period"], "M02")
        self.assertEqual(yoy["value"], "3.5")

    def test_skips_empty_value_for_latest(self):
        only_empty_recent = [
            {"year": "2026", "period": "M03", "value": "", "periodName": "March"},
            {"year": "2026", "period": "M02", "value": "3.8", "periodName": "February"},
        ]
        latest, _ = _pick_latest_and_yoy(only_empty_recent)
        self.assertEqual(latest["period"], "M02")

    def test_no_yoy_returns_none(self):
        single_year = [
            {"year": "2026", "period": "M02", "value": "3.8", "periodName": "February"},
        ]
        _, yoy = _pick_latest_and_yoy(single_year)
        self.assertIsNone(yoy)


if __name__ == "__main__":
    unittest.main()
