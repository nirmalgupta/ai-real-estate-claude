"""Logic tests for the search-side rent enrichment (no network)."""
import unittest

from pipeline.search.rent import (
    BED_SCALAR,
    RentBenchmark,
    _bed_scalar,
    compute_rent_metrics,
    estimate_rent,
)


class TestBedScalar(unittest.TestCase):
    def test_known_table(self):
        self.assertEqual(_bed_scalar(0), 0.6)
        self.assertEqual(_bed_scalar(2), 1.0)
        self.assertEqual(_bed_scalar(4), 1.5)

    def test_5plus_bedrooms_bumps(self):
        self.assertEqual(_bed_scalar(5), 1.75)
        self.assertEqual(_bed_scalar(7), 1.75)

    def test_none_defaults_to_1(self):
        self.assertEqual(_bed_scalar(None), 1.0)


class TestEstimateRent(unittest.TestCase):
    def test_hud_fmr_picks_bedroom_match(self):
        b = RentBenchmark(
            source="hud_fmr",
            fmr_by_bed={0: 1100, 1: 1350, 2: 1700, 3: 2300, 4: 2800},
            acs_median=None, note="",
        )
        rent, label = estimate_rent(beds=3, sqft=2200, bench=b)
        self.assertEqual(rent, 2300)
        self.assertEqual(label, "FMR-3br")

    def test_hud_fmr_clamps_5br_to_4br(self):
        b = RentBenchmark(
            source="hud_fmr",
            fmr_by_bed={0: 1100, 1: 1350, 2: 1700, 3: 2300, 4: 2800},
            acs_median=None, note="",
        )
        rent, _ = estimate_rent(beds=5, sqft=4500, bench=b)
        self.assertEqual(rent, 2800)

    def test_acs_fallback_scales_by_bed(self):
        b = RentBenchmark(
            source="acs_median", fmr_by_bed=None, acs_median=1500, note=""
        )
        rent, label = estimate_rent(beds=3, sqft=2000, bench=b)
        # bed 3 scalar = 1.25, sqft 2000 = no luxury bump
        self.assertEqual(rent, int(1500 * 1.25))
        self.assertIn("ACS", label)

    def test_acs_fallback_luxury_bump(self):
        b = RentBenchmark(
            source="acs_median", fmr_by_bed=None, acs_median=1500, note=""
        )
        rent, _ = estimate_rent(beds=4, sqft=4200, bench=b)
        # bed 4 scalar 1.5 * sqft luxury 1.5 = 2.25
        self.assertEqual(rent, int(1500 * 1.5 * 1.5))

    def test_unavailable_returns_none(self):
        b = RentBenchmark(source="unavailable", fmr_by_bed=None,
                          acs_median=None, note="")
        self.assertIsNone(estimate_rent(beds=3, sqft=2000, bench=b))


class TestComputeRentMetrics(unittest.TestCase):
    def test_known(self):
        # $400k home, $2500/mo rent → GRM = 13.33, cap = (30000*0.55)/400000 = 4.125%
        grm, cap = compute_rent_metrics(400000, 2500)
        self.assertAlmostEqual(grm, 13.3, places=1)
        self.assertAlmostEqual(cap, 0.0413, places=3)

    def test_missing_price(self):
        self.assertEqual(compute_rent_metrics(None, 2500), (None, None))

    def test_missing_rent(self):
        self.assertEqual(compute_rent_metrics(400000, None), (None, None))

    def test_zero_rent(self):
        self.assertEqual(compute_rent_metrics(400000, 0), (None, None))


if __name__ == "__main__":
    unittest.main()
