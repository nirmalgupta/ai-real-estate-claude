"""Logic tests for Chatham CAD sales + improvements joins (no network)."""
import unittest

from pipeline.fetch.county.nc_chatham import (
    _epoch_ms_to_date,
    _parse_sale,
    _parse_structure,
    _pick_latest_valid_sale,
    _pick_primary_structure,
)


class TestEpochMsToDate(unittest.TestCase):
    def test_known_epoch(self):
        # 1772150400000 ms = 2026-02-27 UTC
        self.assertEqual(_epoch_ms_to_date(1772150400000), "2026-02-27")

    def test_placeholder_1899_is_none(self):
        # 12/30/1899 DEVNET "unknown" placeholder = large negative epoch.
        self.assertIsNone(_epoch_ms_to_date(-2209161600000))

    def test_junk_is_none(self):
        for v in (None, "", "2020"):
            self.assertIsNone(_epoch_ms_to_date(v))


class TestPickLatestValidSale(unittest.TestCase):
    SALES = [
        {"date_of_sale": 1778716800000, "gross_selling_price": 0.0, "valid_sale_flag": "N"},
        {"date_of_sale": 1772150400000, "gross_selling_price": 176000.0, "valid_sale_flag": "Y"},
        {"date_of_sale": 1649808000000, "gross_selling_price": 125000.0, "valid_sale_flag": "Y"},
    ]

    def test_picks_latest_valid_with_price(self):
        sale = _pick_latest_valid_sale(self.SALES)
        self.assertEqual(sale["gross_selling_price"], 176000.0)

    def test_skips_invalid_even_if_newer(self):
        # The newest row is flagged N — must be ignored.
        sale = _pick_latest_valid_sale(self.SALES)
        self.assertEqual(sale["valid_sale_flag"], "Y")

    def test_none_when_no_valid(self):
        rows = [{"date_of_sale": 1, "gross_selling_price": 0, "valid_sale_flag": "N"}]
        self.assertIsNone(_pick_latest_valid_sale(rows))

    def test_falls_back_to_net_price(self):
        rows = [{"date_of_sale": 5, "net_selling_price": 99000, "valid_sale_flag": "Y"}]
        self.assertEqual(_pick_latest_valid_sale(rows)["net_selling_price"], 99000)


class TestParseSale(unittest.TestCase):
    def test_parses_price_and_date(self):
        sale = {"date_of_sale": 1772150400000, "gross_selling_price": 176000.0}
        self.assertEqual(
            _parse_sale(sale),
            {"last_sale_price": 176000, "last_sale_date": "2026-02-27"},
        )

    def test_zero_price_skipped(self):
        self.assertEqual(_parse_sale({"gross_selling_price": 0}), {})


class TestStructures(unittest.TestCase):
    def test_picks_largest_living_area(self):
        rows = [
            {"year_built": 1990, "gross_living_area": 1200.0},
            {"year_built": 2001, "gross_living_area": 3075.0},
            {"year_built": 1975, "gross_living_area": 800.0},
        ]
        best = _pick_primary_structure(rows)
        self.assertEqual(best["gross_living_area"], 3075.0)

    def test_parse_structure(self):
        self.assertEqual(
            _parse_structure({"year_built": 1920, "gross_living_area": 3075.0}),
            {"year_built_cad": 1920, "living_area_sqft_cad": 3075},
        )

    def test_parse_structure_skips_zero(self):
        self.assertEqual(
            _parse_structure({"year_built": 0, "gross_living_area": 0}), {}
        )

    def test_pick_none_when_empty(self):
        self.assertIsNone(_pick_primary_structure([]))


if __name__ == "__main__":
    unittest.main()
