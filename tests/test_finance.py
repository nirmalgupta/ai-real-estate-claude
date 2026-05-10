"""Sanity tests for the finance module.

Run: python3 -m unittest tests.test_finance
"""
import unittest

from pipeline.analyze.finance import (
    CashFlowInputs, break_even_purchase_price, buy_hold_irr,
    compute_cash_flow, irr, monthly_pi,
)


class TestMortgageMath(unittest.TestCase):
    def test_monthly_pi_known_value(self):
        # $300K @ 6.5% / 30yr should be ~$1,896.20/mo
        pi = monthly_pi(300_000, 0.065, 30)
        self.assertAlmostEqual(pi, 1896.20, delta=1.0)

    def test_zero_rate(self):
        # $300K at 0% over 30yr → $300K / 360 = $833.33/mo
        pi = monthly_pi(300_000, 0.0, 30)
        self.assertAlmostEqual(pi, 833.33, delta=0.5)


class TestCashFlow(unittest.TestCase):
    def test_break_even_logic(self):
        # Synthetic property, slightly cash-flow positive at $5K rent
        inputs = CashFlowInputs(
            list_price=500_000,
            mortgage_rate=0.06,
            annual_property_tax=6_000,
            annual_insurance=2_000,
            monthly_rent=5_000,
        )
        cf = compute_cash_flow(inputs)
        # GRM = 500K / (5K * 12) = 8.33
        self.assertAlmostEqual(cf.grm, 8.333, delta=0.01)
        # Break-even rent should be > current cash flow when negative,
        # or close to current rent when ~breakeven
        be = cf.break_even_rent()
        self.assertGreater(be, 0)
        self.assertLess(be, 20_000)

    def test_cap_rate_in_band(self):
        inputs = CashFlowInputs(
            list_price=400_000,
            mortgage_rate=0.07,
            annual_property_tax=4_000,
            annual_insurance=1_500,
            monthly_rent=3_500,
        )
        cf = compute_cash_flow(inputs)
        # NOI ~ (3500 * 12 * 0.94) - taxes - insurance - maint - capex - mgmt
        # Expect cap rate roughly in 4-8% range for these inputs
        self.assertGreater(cf.cap_rate, 0.03)
        self.assertLess(cf.cap_rate, 0.10)


class TestBuyHold(unittest.TestCase):
    def test_appreciation_compounds(self):
        inputs = CashFlowInputs(list_price=500_000, mortgage_rate=0.06,
                                monthly_rent=4_000)
        bh = buy_hold_irr(500_000, inputs, hold_years=7, appreciation_rate=0.05)
        # 500K * 1.05^7 ~ 703K
        self.assertAlmostEqual(bh["final_value"], 703_550, delta=1_000)
        # Loan should amortize down
        self.assertLess(bh["remaining_loan_balance"], 400_000)


class TestIRR(unittest.TestCase):
    def test_simple_double_in_one_year(self):
        # -100 today, +200 next year => IRR = 100%
        self.assertAlmostEqual(irr([-100, 200]), 1.0, delta=0.01)

    def test_zero_return(self):
        # -100 today, +100 next year => IRR = 0
        self.assertAlmostEqual(irr([-100, 100]), 0.0, delta=0.01)

    def test_negative_return(self):
        # -100 today, +50 next year => IRR = -50%
        self.assertAlmostEqual(irr([-100, 50]), -0.5, delta=0.01)

    def test_buy_hold_negative_carry(self):
        # Mimics a property that bleeds cash but exits with appreciation
        # close to break-even — IRR should be slightly negative, NOT -10%+.
        # -360K, then -89K/yr for 6 yr, then -89K + 785K at year 7
        cf = [-360_000] + [-89_000] * 6 + [-89_000 + 785_000]
        result = irr(cf)
        self.assertIsNotNone(result)
        # Total return is negative (~$200K loss); IRR should be moderately
        # negative (single digits), not catastrophically so.
        self.assertLess(result, 0)
        self.assertGreater(result, -0.10)

    def test_no_sign_change_returns_none(self):
        # All negative => IRR undefined
        self.assertIsNone(irr([-100, -50, -25]))


class TestBuyHoldIRR(unittest.TestCase):
    def test_irr_present_in_result(self):
        inputs = CashFlowInputs(
            list_price=500_000, mortgage_rate=0.06,
            annual_property_tax=6000, monthly_rent=4_000,
        )
        bh = buy_hold_irr(500_000, inputs, hold_years=5,
                          appreciation_rate=0.04)
        self.assertIn("irr", bh)
        # If multiple > 1, IRR should be positive
        if bh["multiple"] > 1.0:
            self.assertIsNotNone(bh["irr"])
            self.assertGreater(bh["irr"], 0)


class TestBreakEvenPrice(unittest.TestCase):
    def test_break_even_returns_reasonable(self):
        template = CashFlowInputs(list_price=0, mortgage_rate=0.065,
                                  annual_insurance=2_000)
        be = break_even_purchase_price(target_monthly_rent=3_000,
                                       inputs_template=template)
        # At $3K/mo rent, break-even price should be in low-mid 6 figures
        self.assertGreater(be, 100_000)
        self.assertLess(be, 1_000_000)


if __name__ == "__main__":
    unittest.main()
