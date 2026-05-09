---
name: real-estate-rental
description: Quick rent estimate + monthly cash flow projection for a property. Trigger on /real-estate-rental or when the user asks "what would this rent for?", "is this cash-flow positive?", "what's the cap rate?".
---

# Real Estate — Rental & Cash Flow Only

## Steps

1. Normalize the address.
2. Fetch listing for purchase price, bed/bath/sqft, taxes, HOA.
3. Invoke the `re-rental` subagent via `Task`.
4. Write output to `RENTAL-ANALYSIS.md`.

## Output spec

- Estimated monthly rent (low/mid/high) with sources
- Income side: gross rent, vacancy loss (~7%), effective gross income
- Expense side: P&I (assume 20% down, current 30-yr fixed rate), property tax, insurance, HOA, maintenance (1% annual / 12), property mgmt (8% if applicable), CapEx reserve (5%)
- Net cash flow per month
- Cap rate, cash-on-cash return, gross rent multiplier
- Verdict: cash-flow positive / breakeven / negative
- Disclaimer
