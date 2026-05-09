---
name: real-estate-market
description: Quick local market conditions — buyer's vs. seller's market, days on market, inventory, price trends, mortgage rate context. Trigger on /real-estate-market, "what's the market like in X?", "is now a good time to buy?".
---

# Real Estate — Market Conditions Only

## Steps

1. Normalize the address. Extract metro/MSA + ZIP.
2. Invoke the `re-market` subagent via `Task`.
3. Write output to `MARKET-ANALYSIS.md`.

## Output spec

- Verdict: Buyer's / Balanced / Seller's market (with reasoning)
- Median sale price + 12-mo trend (% change)
- Median days on market (vs. 1 yr ago)
- Months of inventory (under 3 = seller's, 3-6 = balanced, over 6 = buyer's)
- Sale-to-list ratio (avg %)
- Active listings vs. recent sales
- Current 30-yr fixed mortgage rate context
- Local catalysts: layoffs, expansions, infrastructure, policy changes
- Disclaimer
