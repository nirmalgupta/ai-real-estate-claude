#!/usr/bin/env python3
"""
Mortgage and investment math helpers.

Usage:
    python3 mortgage_calculator.py --price 450000 --rate 7.25 --down 20
    python3 mortgage_calculator.py --scenarios --price 450000 --rate 7.25 --rent 2750 --tax 8400 --hoa 0 --rehab 30000 --arv 510000
"""
import argparse
import json
import sys


def monthly_pi(loan_amount: float, annual_rate_pct: float, years: int = 30) -> float:
    """Standard amortization: principal + interest payment per month."""
    if loan_amount <= 0:
        return 0.0
    r = annual_rate_pct / 100 / 12
    n = years * 12
    if r == 0:
        return loan_amount / n
    return loan_amount * (r * (1 + r) ** n) / ((1 + r) ** n - 1)


def cash_flow(price, rate_pct, rent, tax_annual, hoa_monthly, *,
              down_pct=20, insurance_pct=0.35, maint_pct=1.0, capex_pct=0.5,
              vacancy_pct=7, mgmt_pct=8) -> dict:
    """Full monthly P&L for a buy-and-hold rental."""
    down = price * down_pct / 100
    loan = price - down
    pi = monthly_pi(loan, rate_pct)
    tax_m = tax_annual / 12
    ins_m = price * insurance_pct / 100 / 12
    maint_m = price * maint_pct / 100 / 12
    capex_m = price * capex_pct / 100 / 12
    vacancy = rent * vacancy_pct / 100
    mgmt = rent * mgmt_pct / 100

    egi = rent - vacancy
    total_exp_self = pi + tax_m + ins_m + hoa_monthly + maint_m + capex_m
    total_exp_mgr = total_exp_self + mgmt
    cf_self = egi - total_exp_self
    cf_mgr = egi - total_exp_mgr

    # Cap rate uses NOI (not subtracting P&I)
    noi_annual = (egi - tax_m - ins_m - hoa_monthly - maint_m - capex_m) * 12
    cap_rate = noi_annual / price * 100

    cash_invested = down + price * 0.03  # closing costs ~3%
    coc_self = cf_self * 12 / cash_invested * 100
    grm = price / (rent * 12)

    return {
        "down_payment": round(down),
        "loan_amount": round(loan),
        "monthly": {
            "rent": round(rent),
            "vacancy": -round(vacancy),
            "egi": round(egi),
            "pi": -round(pi),
            "tax": -round(tax_m),
            "insurance": -round(ins_m),
            "hoa": -round(hoa_monthly),
            "maintenance": -round(maint_m),
            "capex": -round(capex_m),
            "mgmt": -round(mgmt),
        },
        "cash_flow_self_managed": round(cf_self),
        "cash_flow_with_mgr": round(cf_mgr),
        "annual_cash_flow_self": round(cf_self * 12),
        "annual_cash_flow_mgr": round(cf_mgr * 12),
        "cap_rate_pct": round(cap_rate, 2),
        "cash_on_cash_pct": round(coc_self, 2),
        "grm": round(grm, 2),
        "cash_invested": round(cash_invested),
    }


def buy_and_hold_5_10(price, rate_pct, monthly_cf, down_pct=20, appreciation_pct=3.0):
    down = price * down_pct / 100
    loan = price - down
    cash_in = down + price * 0.03
    pi = monthly_pi(loan, rate_pct)

    def project(years):
        # Approx principal paydown via amortization
        r = rate_pct / 100 / 12
        n = years * 12
        balance = loan
        for _ in range(n):
            interest = balance * r
            principal = pi - interest
            balance -= principal
        equity_paydown = loan - balance
        appreciation = price * ((1 + appreciation_pct / 100) ** years - 1)
        cash_flow_total = monthly_cf * 12 * years
        total_gain = equity_paydown + appreciation + cash_flow_total
        roi = total_gain / cash_in * 100
        return {
            "equity_paydown": round(equity_paydown),
            "appreciation": round(appreciation),
            "cash_flow_total": round(cash_flow_total),
            "total_gain": round(total_gain),
            "roi_pct": round(roi, 1),
        }

    return {"5yr": project(5), "10yr": project(10), "cash_invested": round(cash_in)}


def brrrr(price, rehab, arv, rate_pct, refi_ltv=75, hard_money_pts=2, hold_months=6):
    holding_costs = price * 0.005 * hold_months  # rough: tax/ins/utilities
    hard_money_interest = price * 0.10 / 12 * hold_months
    pts = price * hard_money_pts / 100
    total_in = price + rehab + holding_costs + hard_money_interest + pts
    refi_proceeds = arv * refi_ltv / 100
    cash_left = total_in - refi_proceeds
    new_loan = refi_proceeds
    new_pi = monthly_pi(new_loan, rate_pct)
    return {
        "total_invested_at_refi": round(total_in),
        "refi_proceeds": round(refi_proceeds),
        "cash_left_in_deal": round(cash_left),
        "new_monthly_pi": round(new_pi),
        "verdict": (
            "Works" if cash_left < (price + rehab) * 0.10
            else "Marginal" if cash_left < (price + rehab) * 0.20
            else "Fails"
        ),
    }


def fix_and_flip(price, rehab, arv, hold_months=6, hard_money_rate=10, selling_pct=7):
    holding = price * 0.005 * hold_months
    interest = price * hard_money_rate / 100 / 12 * hold_months
    selling = arv * selling_pct / 100
    total_cost = price + rehab + holding + interest + selling
    profit = arv - total_cost
    cash_in = price * 0.10 + rehab  # 10% down hard money + rehab cash
    roi = profit / cash_in * 100 if cash_in > 0 else 0
    return {
        "total_cost": round(total_cost),
        "arv": round(arv),
        "profit": round(profit),
        "cash_invested": round(cash_in),
        "project_roi_pct": round(roi, 1),
        "verdict": (
            "Works" if roi > 20 and profit > 25000
            else "Marginal" if roi > 10
            else "Fails"
        ),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--price", type=float, required=True)
    p.add_argument("--rate", type=float, default=7.25, help="30-yr fixed rate %")
    p.add_argument("--down", type=float, default=20)
    p.add_argument("--rent", type=float, default=0)
    p.add_argument("--tax", type=float, default=0, help="Annual property tax")
    p.add_argument("--hoa", type=float, default=0, help="Monthly HOA")
    p.add_argument("--scenarios", action="store_true",
                   help="Run buy-and-hold + BRRRR + flip scenarios")
    p.add_argument("--rehab", type=float, default=0)
    p.add_argument("--arv", type=float, default=0)
    args = p.parse_args()

    if args.scenarios:
        cf = cash_flow(args.price, args.rate, args.rent, args.tax, args.hoa,
                       down_pct=args.down)
        bh = buy_and_hold_5_10(args.price, args.rate, cf["cash_flow_self_managed"],
                               down_pct=args.down)
        result = {
            "cash_flow": cf,
            "buy_and_hold": bh,
            "brrrr": brrrr(args.price, args.rehab, args.arv, args.rate),
            "fix_and_flip": fix_and_flip(args.price, args.rehab, args.arv),
        }
    elif args.rent > 0:
        result = cash_flow(args.price, args.rate, args.rent, args.tax, args.hoa,
                           down_pct=args.down)
    else:
        result = {
            "monthly_pi": round(monthly_pi(
                args.price * (1 - args.down / 100), args.rate)),
            "down_payment": round(args.price * args.down / 100),
            "loan_amount": round(args.price * (1 - args.down / 100)),
        }

    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
