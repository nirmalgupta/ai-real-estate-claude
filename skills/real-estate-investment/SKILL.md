---
name: real-estate-investment
description: Quick investment-strategy comparison — buy & hold, BRRRR, fix & flip. Returns ROI, ARV, rehab estimates, and 7-yr appreciation projection. Trigger on /real-estate-investment, "should I flip this?", "BRRRR analysis", "what's the ROI?".
---

# Real Estate — Investment Scenarios Only

## Steps

1. Normalize the address.
2. Fetch listing for purchase price + condition signals (year built, "needs updating", photos).
3. Invoke the `re-investment` subagent via `Task`.
4. Write output to `INVESTMENT-ANALYSIS.md`.

## Output spec

Three scenario tables:

**Buy & Hold (5-yr & 10-yr)**
- Total cash invested, monthly cash flow, equity build, appreciation, total ROI

**BRRRR**
- Purchase, rehab estimate, ARV, refi loan amount, cash left in deal, monthly cash flow

**Fix & Flip**
- Purchase, rehab, holding costs (6 mo), selling costs (~7%), ARV, projected profit, project ROI

Conclude with: which strategy works (if any), suggested offer range to make the numbers work, and key risks. Disclaimer.
