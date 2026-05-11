"""Logic tests for the composite-score synthesizer."""
import unittest

from pipeline.synthesize import (
    _score_cash_flow,
    _score_flood,
    _score_irr,
    _score_schools,
    _score_storms,
    _score_walkability,
    composite_score,
)


class TestIndividualScorers(unittest.TestCase):
    def test_cash_flow_high_cap_rate(self):
        computed = {"cash_flow": {"cap_rate": 0.08}}
        self.assertGreater(_score_cash_flow(computed, {}), 80)

    def test_cash_flow_missing(self):
        self.assertIsNone(_score_cash_flow({}, {}))

    def test_flood_zone_x_high_score(self):
        self.assertGreater(_score_flood({}, {"flood_zone": "X"}), 90)

    def test_flood_zone_ve_low_score(self):
        self.assertLess(_score_flood({}, {"flood_zone": "VE"}), 20)

    def test_flood_nfip_claims_degrade(self):
        score_with_claims = _score_flood({}, {"flood_zone": "X",
                                              "nfip_claims_count_10yr": 60})
        score_clean = _score_flood({}, {"flood_zone": "X"})
        self.assertLess(score_with_claims, score_clean)

    def test_storms_zero_events_high(self):
        s = _score_storms({}, {"hail_within_10mi_10yr": 0,
                               "tornadoes_within_10mi_10yr": 0})
        self.assertEqual(s, 100)

    def test_storms_many_events_low(self):
        s = _score_storms({}, {"hail_within_10mi_10yr": 50,
                               "tornadoes_within_10mi_10yr": 10})
        self.assertLess(s, 30)

    def test_schools_close_high(self):
        s = _score_schools({}, {
            "nearest_elementary_distance_miles": 0.5,
            "nearest_middle_distance_miles": 1.0,
            "nearest_high_distance_miles": 1.5,
        })
        self.assertGreater(s, 80)

    def test_walkability_picks_min(self):
        s = _score_walkability({}, {
            "nearest_supermarket_miles": 5.0,
            "nearest_pharmacy_miles": 0.25,
        })
        self.assertGreater(s, 90)

    def test_irr_uses_5pct_sensitivity_row(self):
        computed = {"buy_hold": {"sensitivity": [
            {"appreciation_rate": 0.03, "irr": 0.04},
            {"appreciation_rate": 0.05, "irr": 0.085},
            {"appreciation_rate": 0.07, "irr": 0.12},
        ]}}
        s = _score_irr(computed, {})
        # IRR 8.5% → (8.5 - 1) * 14 = 105 → clamped to 100
        self.assertEqual(s, 100)


class TestCompositeScore(unittest.TestCase):
    def test_redistributes_missing_signals(self):
        """A property with only 2 signals should still produce a usable score."""
        computed = {"cash_flow": {"cap_rate": 0.06, "cash_on_cash": 0.10}}
        facts = {}
        result = composite_score(computed, facts)
        # The two cash signals should pick up the entire weight budget
        self.assertAlmostEqual(
            sum(result["weights"].values()), 1.0, places=2
        )
        self.assertIn("flood", result["missing"])

    def test_full_signal_property(self):
        computed = {
            "cash_flow": {"cap_rate": 0.06, "cash_on_cash": 0.10},
            "buy_hold": {"sensitivity": [
                {"appreciation_rate": 0.05, "irr": 0.10}
            ]},
            "inputs": {"list_price": 500000, "annual_property_tax": 8000},
        }
        facts = {
            "flood_zone": "X",
            "hail_within_10mi_10yr": 2,
            "tornadoes_within_10mi_10yr": 0,
            "seismic_pga_2pct_50yr": 0.05,
            "nearest_elementary_distance_miles": 1.0,
            "nearest_middle_distance_miles": 1.5,
            "nearest_high_distance_miles": 2.0,
            "nearest_supermarket_miles": 0.5,
            "median_household_income": 95000,
            "redfin_implied_list_appreciation": {"implied_annual_rate": 0.04},
        }
        result = composite_score(computed, facts)
        self.assertEqual(result["missing"], [])
        # Decent property in zone X with full data should land in B/A
        self.assertGreaterEqual(result["score"], 65)

    def test_total_data_loss_returns_floor(self):
        result = composite_score({}, {})
        self.assertEqual(result["score"], 0.0)
        self.assertEqual(result["grade"], "F")
        # All 11 signals should be in missing
        self.assertEqual(len(result["missing"]), 11)

    def test_subscores_match_weights_keys(self):
        computed = {"cash_flow": {"cap_rate": 0.05}}
        result = composite_score(computed, {"flood_zone": "X"})
        self.assertEqual(set(result["subscores"]), set(result["weights"]))


if __name__ == "__main__":
    unittest.main()
