"""Logic tests for analyze.defaults (no network)."""
import unittest

from pipeline.analyze.defaults import (
    STATE_TAX_RATE,
    _high_risk_flood,
    _parse_pmms_latest,
    default_insurance,
    default_rent,
    default_tax,
)


class TestDefaultRent(unittest.TestCase):
    def test_prefers_hud_fmr_for_matched_beds(self):
        facts = {"fmr_3br": 2400, "median_gross_rent": 1800, "sqft": 2500}
        rent, src = default_rent(facts, beds=3)
        self.assertEqual(rent, 2400)
        self.assertIn("fmr_3br", src)

    def test_falls_back_to_acs(self):
        facts = {"median_gross_rent": 1800, "sqft": 2500}
        rent, src = default_rent(facts, beds=3)
        self.assertEqual(rent, 1800)
        self.assertIn("ACS", src)

    def test_acs_luxury_scaling(self):
        facts = {"median_gross_rent": 1800, "sqft": 4500}
        rent, src = default_rent(facts, beds=5)
        self.assertEqual(rent, 4500)
        self.assertIn("luxury", src)

    def test_hud_5br_clamps_to_4br(self):
        facts = {"fmr_4br": 3200, "median_gross_rent": 1800}
        rent, src = default_rent(facts, beds=5)
        self.assertEqual(rent, 3200)
        self.assertIn("fmr_4br", src)

    def test_zero_when_no_facts(self):
        rent, src = default_rent({}, beds=3)
        self.assertEqual(rent, 0.0)
        self.assertIn("--rent", src)


class TestDefaultTax(unittest.TestCase):
    def test_prefers_assessed_value(self):
        facts = {"tax_assessed_value": 800000}
        tax, src = default_tax(facts, list_price=1000000, state="TX")
        # TX rate = 1.90% → 800000 * 0.019 = 15200
        self.assertAlmostEqual(tax, 15200, places=0)
        self.assertIn("CAD assessed", src)
        self.assertIn("TX", src)

    def test_falls_back_to_list_price(self):
        facts = {}
        tax, src = default_tax(facts, list_price=500000, state="FL")
        # FL rate = 0.91% → 4550
        self.assertAlmostEqual(tax, 4550, places=0)
        self.assertIn("list_price", src)

    def test_unknown_state_uses_2pct(self):
        facts = {}
        tax, src = default_tax(facts, list_price=100000, state="ZZ")
        self.assertEqual(tax, 2000)


class TestDefaultInsurance(unittest.TestCase):
    def test_base_rate(self):
        ins, src = default_insurance({"flood_zone": "X"}, list_price=500000)
        self.assertEqual(ins, 2000)
        self.assertIn("0.40%", src)

    def test_high_risk_flood_zone(self):
        ins, src = default_insurance({"flood_zone": "AE"}, list_price=500000)
        # base + flood bump = 0.4% + 0.4% = 0.8%
        self.assertEqual(ins, 4000)
        self.assertIn("SFHA", src)

    def test_high_hail_bumps_rate(self):
        ins, _ = default_insurance(
            {"flood_zone": "X", "hail_within_10mi_10yr": 10},
            list_price=500000,
        )
        # base 0.4% + hail 0.2% = 0.6%
        self.assertEqual(ins, 3000)

    def test_multiple_bumps_stack(self):
        ins, src = default_insurance(
            {"flood_zone": "AE",
             "hail_within_10mi_10yr": 12,
             "nfip_claims_count_10yr": 50},
            list_price=500000,
        )
        # base 0.4% + flood 0.4% + hail 0.2% + nfip 0.2% = 1.2%
        self.assertEqual(ins, 6000)
        self.assertIn("SFHA", src)
        self.assertIn("hail", src)
        self.assertIn("NFIP", src)


class TestHighRiskFlood(unittest.TestCase):
    def test_known_sfha_zones(self):
        for z in ("A", "AE", "AH", "AO", "AR", "V", "VE"):
            self.assertTrue(_high_risk_flood(z))

    def test_x_zone_is_low_risk(self):
        self.assertFalse(_high_risk_flood("X"))

    def test_none_or_empty(self):
        self.assertFalse(_high_risk_flood(None))
        self.assertFalse(_high_risk_flood(""))


class TestParsePmmsLatest(unittest.TestCase):
    def test_picks_most_recent_row(self):
        csv = (
            "Header,line,here\n"
            "Date,30-Yr FRM,15-Yr FRM\n"
            "01/02/2025,6.65,5.92\n"
            "01/09/2025,6.70,5.95\n"
            "01/16/2025,6.55,5.85\n"
        )
        result = _parse_pmms_latest(csv)
        self.assertIsNotNone(result)
        rate, week = result
        self.assertEqual(rate, 6.55)
        self.assertEqual(week, "2025-01-16")

    def test_skips_unparseable(self):
        csv = (
            "garbage,row\n"
            "01/02/2025,6.65\n"
            "not-a-date,5.50\n"
            "01/09/2025,abc\n"
        )
        result = _parse_pmms_latest(csv)
        self.assertEqual(result[0], 6.65)


class TestStateTable(unittest.TestCase):
    def test_all_50_states_covered(self):
        for s in ("CA", "TX", "FL", "NY", "NC", "WA", "IL", "AK", "HI"):
            self.assertIn(s, STATE_TAX_RATE)
        # Should be 50 states + DC
        self.assertEqual(len(STATE_TAX_RATE), 51)


if __name__ == "__main__":
    unittest.main()
