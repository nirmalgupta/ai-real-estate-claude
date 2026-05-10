"""Deterministic financial math for the analysis layer.

All numbers go through here so the LLM never needs to do arithmetic.
Functions accept primitive args, return primitive results — caller is
responsible for sourcing inputs from the wiki.
"""
from __future__ import annotations

from dataclasses import dataclass


def monthly_pi(principal: float, annual_rate: float, term_years: int = 30) -> float:
    """Monthly principal + interest payment for a fixed-rate mortgage."""
    if annual_rate == 0:
        return principal / (term_years * 12)
    r = annual_rate / 12
    n = term_years * 12
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)


def irr(
    cash_flows: list[float],
    lo: float = -0.999,
    hi: float = 10.0,
    tol: float = 1.0,
    max_iter: int = 200,
) -> float | None:
    """Internal Rate of Return via bisection.

    cash_flows[0] is the year-0 investment (typically negative);
    cash_flows[1..N] are end-of-period returns. Returns the rate r
    where NPV(r) == 0, or None if no sign change exists in [lo, hi]
    (e.g., all flows have the same sign — IRR is undefined).
    """
    def npv(r: float) -> float:
        return sum(cf / (1 + r) ** t for t, cf in enumerate(cash_flows))

    npv_lo, npv_hi = npv(lo), npv(hi)
    if npv_lo == 0:
        return lo
    if npv_hi == 0:
        return hi
    if npv_lo * npv_hi > 0:
        return None  # no root in bracket

    for _ in range(max_iter):
        mid = (lo + hi) / 2
        v = npv(mid)
        if abs(v) < tol:
            return mid
        if npv(lo) * v < 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


@dataclass
class CashFlowInputs:
    list_price: float
    down_pct: float = 0.20
    mortgage_rate: float = 0.0675
    term_years: int = 30
    annual_property_tax: float = 0.0          # $ per year
    annual_insurance: float = 0.0
    monthly_hoa: float = 0.0
    monthly_pool_maintenance: float = 0.0
    maintenance_pct: float = 0.01             # of list_price per year
    capex_pct: float = 0.005
    vacancy_pct: float = 0.06
    property_mgmt_pct: float = 0.09           # of gross rent
    monthly_rent: float = 0.0


@dataclass
class CashFlowResult:
    monthly_pi: float
    monthly_tax: float
    monthly_insurance: float
    monthly_hoa: float
    monthly_pool: float
    monthly_maintenance: float
    monthly_capex: float
    monthly_vacancy: float
    monthly_mgmt: float
    monthly_gross_rent: float
    monthly_egi: float                        # effective gross income
    monthly_total_expenses: float
    monthly_cash_flow_no_pm: float            # self-managed
    monthly_cash_flow_with_pm: float
    annual_cash_flow_with_pm: float
    cap_rate: float                           # NOI / price
    grm: float                                # price / annual gross rent
    cash_invested: float
    cash_on_cash: float                       # annual_CF / cash_invested

    def break_even_rent(self) -> float:
        """Monthly rent needed for $0 cash flow with a property manager.

        Closed-form: solve for rent in:
            rent * (1 - vacancy) - rent * pm_pct - other_fixed - PI = 0
        => rent * (1 - vacancy - pm_pct) = other_fixed + PI
        """
        other_fixed = (
            self.monthly_pi + self.monthly_tax + self.monthly_insurance
            + self.monthly_hoa + self.monthly_pool + self.monthly_maintenance
            + self.monthly_capex
        )
        denom = 1 - (self.monthly_vacancy / max(self.monthly_gross_rent, 1)) \
                  - (self.monthly_mgmt / max(self.monthly_gross_rent, 1))
        if denom <= 0:
            return float("inf")
        return other_fixed / denom


def compute_cash_flow(inputs: CashFlowInputs) -> CashFlowResult:
    loan = inputs.list_price * (1 - inputs.down_pct)
    pi = monthly_pi(loan, inputs.mortgage_rate, inputs.term_years)

    tax_m = inputs.annual_property_tax / 12
    ins_m = inputs.annual_insurance / 12
    maint_m = inputs.list_price * inputs.maintenance_pct / 12
    capex_m = inputs.list_price * inputs.capex_pct / 12

    gross = inputs.monthly_rent
    vac_m = gross * inputs.vacancy_pct
    egi = gross - vac_m
    mgmt_m = gross * inputs.property_mgmt_pct

    fixed_expenses = (
        pi + tax_m + ins_m + inputs.monthly_hoa + inputs.monthly_pool_maintenance
        + maint_m + capex_m
    )
    cf_no_pm = egi - fixed_expenses
    cf_with_pm = cf_no_pm - mgmt_m

    annual_noi = (egi - tax_m - ins_m - inputs.monthly_hoa
                  - inputs.monthly_pool_maintenance - maint_m
                  - capex_m - mgmt_m) * 12
    cap_rate = annual_noi / inputs.list_price if inputs.list_price else 0.0
    grm = inputs.list_price / (gross * 12) if gross else 0.0

    cash_invested = inputs.list_price * inputs.down_pct + inputs.list_price * 0.03
    annual_cf = cf_with_pm * 12
    coc = annual_cf / cash_invested if cash_invested else 0.0

    return CashFlowResult(
        monthly_pi=pi,
        monthly_tax=tax_m,
        monthly_insurance=ins_m,
        monthly_hoa=inputs.monthly_hoa,
        monthly_pool=inputs.monthly_pool_maintenance,
        monthly_maintenance=maint_m,
        monthly_capex=capex_m,
        monthly_vacancy=vac_m,
        monthly_mgmt=mgmt_m,
        monthly_gross_rent=gross,
        monthly_egi=egi,
        monthly_total_expenses=fixed_expenses + mgmt_m,
        monthly_cash_flow_no_pm=cf_no_pm,
        monthly_cash_flow_with_pm=cf_with_pm,
        annual_cash_flow_with_pm=annual_cf,
        cap_rate=cap_rate,
        grm=grm,
        cash_invested=cash_invested,
        cash_on_cash=coc,
    )


def buy_hold_irr(
    list_price: float,
    inputs: CashFlowInputs,
    hold_years: int = 7,
    appreciation_rate: float = 0.045,
    selling_costs_pct: float = 0.07,
) -> dict[str, float | None]:
    """N-year buy-and-hold returns with proper IRR.

    Simple model: constant annual operating cash flow, exit at year-N
    value minus selling costs and remaining loan balance. Cash flow
    schedule:
        t=0:        -cash_invested            (down + closing)
        t=1..N-1:   annual_cash_flow          (operating, often negative)
        t=N:        annual_cash_flow + net_proceeds   (operating + exit)

    Returns a dict with final_value, net_proceeds, total_cf, multiple,
    and `irr` — the discount rate that zeroes NPV across the schedule.
    `irr` is None if the cash flow series doesn't have a sign change
    (e.g., never recovers initial investment under any positive rate).
    """
    cf_year = compute_cash_flow(inputs).annual_cash_flow_with_pm
    final_value = list_price * (1 + appreciation_rate) ** hold_years
    selling_costs = final_value * selling_costs_pct

    # Remaining loan balance after `hold_years` of payments
    loan = list_price * (1 - inputs.down_pct)
    r = inputs.mortgage_rate / 12
    n = inputs.term_years * 12
    k = hold_years * 12
    if r == 0:
        remaining_loan = loan - (loan / n) * k
    else:
        remaining_loan = (
            loan * (1 + r) ** k
            - monthly_pi(loan, inputs.mortgage_rate, inputs.term_years)
              * ((1 + r) ** k - 1) / r
        )
    remaining_loan = max(0.0, remaining_loan)

    net_proceeds = final_value - selling_costs - remaining_loan
    total_cf = cf_year * hold_years
    cash_in = list_price * inputs.down_pct + list_price * 0.03
    total_return = total_cf + net_proceeds - cash_in
    multiple = (total_cf + net_proceeds) / cash_in if cash_in else 0.0

    # Build the cash flow schedule and compute proper IRR
    schedule = [-cash_in]
    for year in range(1, hold_years):
        schedule.append(cf_year)
    schedule.append(cf_year + net_proceeds)
    annual_irr = irr(schedule)

    return {
        "hold_years": hold_years,
        "annual_cash_flow": cf_year,
        "total_cash_flow": total_cf,
        "final_value": final_value,
        "selling_costs": selling_costs,
        "remaining_loan_balance": remaining_loan,
        "net_proceeds": net_proceeds,
        "cash_invested": cash_in,
        "total_return": total_return,
        "multiple": multiple,
        "irr": annual_irr,
        "cash_flow_schedule": schedule,
    }


def break_even_purchase_price(
    target_monthly_rent: float,
    target_monthly_cash_flow: float = 0.0,
    inputs_template: CashFlowInputs | None = None,
) -> float:
    """Iteratively find the purchase price at which monthly cash flow
    (with PM) hits the target. Bisect search; bounds 50K..100M."""
    template = inputs_template or CashFlowInputs(list_price=0.0)

    def cf_at(price: float) -> float:
        i = CashFlowInputs(
            list_price=price,
            down_pct=template.down_pct,
            mortgage_rate=template.mortgage_rate,
            term_years=template.term_years,
            annual_property_tax=price * 0.02,   # rough TX-ish reassessment
            annual_insurance=template.annual_insurance,
            monthly_hoa=template.monthly_hoa,
            monthly_pool_maintenance=template.monthly_pool_maintenance,
            maintenance_pct=template.maintenance_pct,
            capex_pct=template.capex_pct,
            vacancy_pct=template.vacancy_pct,
            property_mgmt_pct=template.property_mgmt_pct,
            monthly_rent=target_monthly_rent,
        )
        return compute_cash_flow(i).monthly_cash_flow_with_pm

    lo, hi = 50_000.0, 100_000_000.0
    for _ in range(80):
        mid = (lo + hi) / 2
        cf = cf_at(mid)
        if abs(cf - target_monthly_cash_flow) < 5.0:
            return mid
        if cf > target_monthly_cash_flow:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2
