"""Logic tests for the Harris CAD geohwp year-built/living-area join (no network)."""
import unittest

from pipeline.fetch.county.tx_harris import _parse_geohwp_attrs, _to_int


class TestToInt(unittest.TestCase):
    def test_string_int(self):
        self.assertEqual(_to_int("1915"), 1915)

    def test_string_float(self):
        self.assertEqual(_to_int("3040.0"), 3040)

    def test_numeric(self):
        self.assertEqual(_to_int(3040), 3040)

    def test_commas(self):
        self.assertEqual(_to_int("3,040"), 3040)

    def test_blank_and_junk(self):
        for v in ("", " ", None, "n/a"):
            self.assertIsNone(_to_int(v))


class TestParseGeohwp(unittest.TestCase):
    def test_residential(self):
        attrs = {"YEAR_BUILT": "1915", "IMPR_SQ_FT": "3040", "TOTIMPSQFT": 3040}
        self.assertEqual(
            _parse_geohwp_attrs(attrs),
            {"year_built_cad": 1915, "living_area_sqft_cad": 3040},
        )

    def test_prefers_numeric_totimpsqft_but_falls_back(self):
        # TOTIMPSQFT missing → fall back to IMPR_SQ_FT string.
        attrs = {"YEAR_BUILT": "1980", "IMPR_SQ_FT": "2200"}
        self.assertEqual(
            _parse_geohwp_attrs(attrs),
            {"year_built_cad": 1980, "living_area_sqft_cad": 2200},
        )

    def test_commercial_nulls_yield_nothing(self):
        attrs = {"YEAR_BUILT": None, "IMPR_SQ_FT": None, "TOTIMPSQFT": None}
        self.assertEqual(_parse_geohwp_attrs(attrs), {})

    def test_zero_year_and_area_skipped(self):
        attrs = {"YEAR_BUILT": "0", "IMPR_SQ_FT": "0", "TOTIMPSQFT": 0}
        self.assertEqual(_parse_geohwp_attrs(attrs), {})

    def test_partial_year_only(self):
        attrs = {"YEAR_BUILT": "2005", "TOTIMPSQFT": 0}
        self.assertEqual(_parse_geohwp_attrs(attrs), {"year_built_cad": 2005})


if __name__ == "__main__":
    unittest.main()
