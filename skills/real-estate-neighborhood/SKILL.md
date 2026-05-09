---
name: real-estate-neighborhood
description: Quick neighborhood quality scorecard — schools, crime, walkability, demographics, growth. Trigger on /real-estate-neighborhood or when the user asks "is this a good area?", "what are the schools like?", "is it safe?".
---

# Real Estate — Neighborhood Only

## Steps

1. Normalize the address. Extract ZIP and city/county.
2. Invoke the `re-neighborhood` subagent via `Task`.
3. Write output to `NEIGHBORHOOD-ANALYSIS.md`.

## Output spec

- Composite neighborhood score (0-100)
- Schools: GreatSchools rating per assigned school, district overall
- Safety: crime index vs. national, recent trend
- Walkability: WalkScore, BikeScore, TransitScore
- Demographics: median household income, median age, owner-occupancy %
- Economy: unemployment, top employers, recent layoffs/expansions
- Growth: 5-yr population trend, building permits, planned developments
- Red flags: anything notable (flood zone, environmental, planned highway, etc.)
- Disclaimer
