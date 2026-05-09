---
name: real-estate-comps
description: Quick comparable-sales analysis for a single property. Pulls 5-7 recent comps within ~1 mile, normalizes for sqft/bed/bath/condition, and returns a fair-market-value range. Trigger on /real-estate-comps or when the user asks "what should I pay for X?", "what are comps near X?", "is this overpriced?".
---

# Real Estate — Comparable Sales Only

Single-agent quick command. Skips the full audit and runs only the comps analysis.

## Steps

1. Normalize the address.
2. Fetch the listing (Zillow/Redfin/Realtor.com) to get bed/bath/sqft/year.
3. Invoke the `re-comps` subagent via the `Task` tool, passing the property facts.
4. Write the agent's output to `COMPS-ANALYSIS.md`.
5. Tell the user the fair-market-value range and how it compares to the list price.

## Output spec

`COMPS-ANALYSIS.md` should include:
- Fair-market-value range (low/mid/high)
- 5-7 comps as a table: address, sale price, $/sqft, sqft, bed/bath, sale date, distance, condition notes
- Comparison vs. list price (over/under by $X and Y%)
- Confidence note (how recent are comps, how close to subject)
- Disclaimer
