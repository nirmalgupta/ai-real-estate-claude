"""CLI: compute deterministic numbers from a wiki property page.

    python -m pipeline.analyze.compute <slug-or-path> \\
        --rate 0.0675 --rent 8500 --tax 17964 --insurance 6500 \\
        --hoa-monthly 0 --pool-monthly 200

Reads:  wiki/properties/<slug>.md
Writes: reports/<slug>/computed.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from pipeline.analyze.defaults import (
    default_insurance, default_mortgage_rate, default_rent, default_tax,
)
from pipeline.analyze.finance import (
    CashFlowInputs, break_even_purchase_price, buy_hold_irr, compute_cash_flow,
)
from pipeline.analyze.wiki_loader import load_wiki_facts

DEFAULT_REPO = Path(__file__).resolve().parent.parent.parent
DEFAULT_WIKI = DEFAULT_REPO / "wiki"
DEFAULT_REPORTS = DEFAULT_REPO / "reports"


def _resolve_wiki_path(arg: str) -> Path:
    p = Path(arg)
    if p.exists() and p.suffix == ".md":
        return p
    candidate = DEFAULT_WIKI / "properties" / f"{arg}.md"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"No wiki page at {p} or {candidate}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Compute financial numbers from a wiki page.")
    p.add_argument("slug", help="Address slug or path to wiki .md file")
    p.add_argument("--rate", type=float, default=None,
                   help="30-yr fixed mortgage rate (decimal). Defaults to "
                        "Freddie Mac PMMS latest weekly rate.")
    p.add_argument("--down-pct", type=float, default=0.20)
    p.add_argument("--rent", type=float, default=None,
                   help="Estimated monthly rent. Defaults to ACS median * 3 if listing is luxury "
                        "(>2x tract median home value), else ACS median.")
    p.add_argument("--tax", type=float, default=None,
                   help="Annual property tax. Defaults to 2%% of list price (TX-ish post-sale reassessment).")
    p.add_argument("--insurance", type=float, default=None,
                   help="Annual homeowners + pool insurance. Defaults to 0.4%% of list price.")
    p.add_argument("--hoa-monthly", type=float, default=0.0)
    p.add_argument("--pool-monthly", type=float, default=0.0)
    p.add_argument("--maintenance-pct", type=float, default=0.01)
    p.add_argument("--vacancy-pct", type=float, default=0.06)
    p.add_argument("--mgmt-pct", type=float, default=0.09)
    p.add_argument("--hold-years", type=int, default=7)
    p.add_argument("--appreciation", type=float, default=0.045)
    p.add_argument("--reports", type=Path, default=DEFAULT_REPORTS,
                   help="Reports root (default: ./reports)")
    args = p.parse_args(argv)

    wiki_path = _resolve_wiki_path(args.slug)
    fm, facts = load_wiki_facts(wiki_path)

    list_price = facts.get("list_price")
    price_source = "list_price"
    if list_price is None:
        list_price = facts.get("redfin_estimate")
        price_source = "redfin_estimate (off-market home — Redfin AVM)"
    if list_price is None:
        print("ERROR: no list_price or redfin_estimate in wiki facts. "
              "Was Redfin run?", file=sys.stderr)
        return 1

    state = fm.get("state_abbr") or fm.get("state")
    beds = facts.get("beds")

    if args.tax is not None:
        tax, tax_source = float(args.tax), "explicit --tax"
    else:
        tax, tax_source = default_tax(facts, float(list_price), state)

    if args.insurance is not None:
        insurance, insurance_source = float(args.insurance), "explicit --insurance"
    else:
        insurance, insurance_source = default_insurance(facts, float(list_price))

    if args.rent is not None:
        rent, rent_source = float(args.rent), "explicit --rent"
    else:
        rent, rent_source = default_rent(facts, beds=beds)

    if args.rate is not None:
        rate, rate_source = float(args.rate), "explicit --rate"
    else:
        rate, rate_source = default_mortgage_rate()

    inputs = CashFlowInputs(
        list_price=float(list_price),
        down_pct=args.down_pct,
        mortgage_rate=rate,
        annual_property_tax=tax,
        annual_insurance=insurance,
        monthly_hoa=args.hoa_monthly,
        monthly_pool_maintenance=args.pool_monthly,
        maintenance_pct=args.maintenance_pct,
        vacancy_pct=args.vacancy_pct,
        property_mgmt_pct=args.mgmt_pct,
        monthly_rent=rent,
    )

    cf = compute_cash_flow(inputs)
    bh = buy_hold_irr(float(list_price), inputs,
                      hold_years=args.hold_years,
                      appreciation_rate=args.appreciation)
    be_price = break_even_purchase_price(rent, 0.0, inputs)

    report_dir = args.reports / fm["slug"]
    report_dir.mkdir(parents=True, exist_ok=True)

    out = {
        "address": fm["address"],
        "slug": fm["slug"],
        "inputs": {
            "list_price": list_price,
            "list_price_source": price_source,
            "down_pct": args.down_pct,
            "mortgage_rate": rate,
            "mortgage_rate_source": rate_source,
            "annual_property_tax": tax,
            "annual_property_tax_source": tax_source,
            "annual_insurance": insurance,
            "annual_insurance_source": insurance_source,
            "monthly_hoa": args.hoa_monthly,
            "monthly_pool": args.pool_monthly,
            "estimated_monthly_rent": rent,
            "rent_source": rent_source,
        },
        "cash_flow": asdict(cf),
        "buy_hold": bh,
        "break_even_purchase_price": be_price,
        "break_even_rent_with_pm": cf.break_even_rent(),
    }
    out_path = report_dir / "computed.json"
    out_path.write_text(json.dumps(out, indent=2))

    print(f"Wrote {out_path}")
    print(f"  list price:           ${list_price:>12,.0f}  ({price_source})")
    print(f"  mortgage rate:         {rate * 100:>11,.2f}%  ({rate_source})")
    print(f"  annual property tax:  ${tax:>12,.0f}  ({tax_source})")
    print(f"  annual insurance:     ${insurance:>12,.0f}  ({insurance_source})")
    print(f"  est. monthly rent:    ${rent:>12,.0f}  ({rent_source})")
    print(f"  monthly cash flow:    ${cf.monthly_cash_flow_with_pm:>12,.0f}  (with PM, mid case)")
    print(f"  cap rate:              {cf.cap_rate * 100:>11,.2f}%")
    print(f"  cash-on-cash:          {cf.cash_on_cash * 100:>11,.2f}%")
    print(f"  break-even rent:      ${cf.break_even_rent():>12,.0f}")
    print(f"  break-even price:     ${be_price:>12,.0f}")
    if bh.get("irr") is not None:
        print(f"  {args.hold_years}-yr IRR:              {bh['irr'] * 100:>11,.2f}%  (@ {args.appreciation*100:.1f}% appreciation)")
    else:
        print(f"  {args.hold_years}-yr IRR:              undefined (no sign change in cash flow)")

    print()
    print(f"  {args.hold_years}-yr appreciation sensitivity:")
    print(f"  {'rate':>8} {'final value':>15} {'net proceeds':>15} {'total return':>15} {'IRR':>9}")
    for row in bh.get("sensitivity", []):
        rate = row["appreciation_rate"]
        irr_str = f"{row['irr'] * 100:>8.2f}%" if row.get("irr") is not None else "      n/a"
        print(
            f"  {rate*100:>7.1f}% "
            f"${row['final_value']:>13,.0f} "
            f"${row['net_proceeds']:>13,.0f} "
            f"${row['total_return']:>13,.0f} "
            f"{irr_str}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
