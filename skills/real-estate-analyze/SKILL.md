---
name: real-estate-analyze
description: Flagship full property audit. Runs a 3-phase pipeline (discovery → 5 parallel agents → synthesis) and produces PROPERTY-ANALYSIS.md with a 0-100 composite score, comps, cash flow, neighborhood quality, investment scenarios, and market conditions. Trigger when the user runs /real-estate-analyze with an address, or asks for a "full real estate analysis" of a property.
---

# Real Estate — Full Property Analysis

Run a complete investment-grade audit of a single property. Three phases, ~3-5 minutes end-to-end.

## Inputs

The user provides a property address (or listing URL). Normalize to: `123 Main St, City, ST 12345`.

---

## Phase 1 — Discovery (sequential, ~30 sec)

Goal: build a `property_facts` dict that all downstream agents will share.

1. **Fetch the listing.** If the user gave a URL, `WebFetch` it. Otherwise `WebSearch` for `"<address>" zillow OR redfin OR realtor.com` and fetch the top result.
2. **Extract structured facts:**
   - List price, bed/bath count, sqft, lot size, year built, property type
   - Days on market, last sale price + date, price history
   - HOA dues, property tax (annual), listing description
3. **Run the helper script** (optional, only if Python available):
   ```
   python3 ~/.claude/scripts/analyze_property.py "<address>"
   ```
   It does best-effort Zillow/Redfin scraping and writes `property_facts.json` to the cwd.
4. **Persist** the facts dict to `property_facts.json`. All Phase 2 agents read from this file.

If listing can't be located, ask the user for the listing URL before continuing.

---

## Phase 2 — Parallel agents (~2 min)

**Use the `Task` tool to launch all 5 subagents simultaneously in a single message.** Pass each one the `property_facts.json` path as context.

| Agent | Subagent type | Output file | Weight |
|---|---|---|---|
| Comparable sales | `re-comps` | `agent-comps.md` | 25% |
| Rental income & cash flow | `re-rental` | `agent-rental.md` | 20% |
| Neighborhood quality | `re-neighborhood` | `agent-neighborhood.md` | 20% |
| Investment analysis | `re-investment` | `agent-investment.md` | 15% |
| Market conditions | `re-market` | `agent-market.md` | 20% |

**Important:** All 5 `Task` calls go in ONE message so they run in parallel. Sequential calls defeat the architecture and waste time.

Wait for all 5 to return before moving to Phase 3.

---

## Phase 3 — Synthesis (~30 sec)

1. **Read all 5 agent output files.**
2. **Compute composite score** by calling:
   ```
   python3 ~/.claude/scripts/score_property.py
   ```
   It reads the 5 agent files and writes `composite_score.json` with:
   - `score` (0-100)
   - `grade` (A+ / A / B / C / D)
   - `signal` (Strong Buy / Buy / Hold / Watch / Avoid)
   - Per-dimension subscores
3. **Assemble** `PROPERTY-ANALYSIS.md` using this structure:

```markdown
# Property Analysis: <address>

**Score:** <score>/100 · **Grade:** <grade> · **Signal:** <signal>

> AI-generated estimates. Not financial or investment advice. Consult a licensed real estate professional.

## Score Dashboard
| Dimension | Score | Weight |
|---|---|---|
| Comparable Value | XX/100 | 25% |
| Income Potential | XX/100 | 20% |
| Neighborhood Quality | XX/100 | 20% |
| Investment Upside | XX/100 | 15% |
| Market Conditions | XX/100 | 20% |

## The Story
<2-3 sentence narrative: what's the headline, who is this property for, what's the catch>

## Comparable Sales
<paste content from agent-comps.md>

## Rental & Cash Flow
<paste content from agent-rental.md>

## Neighborhood
<paste content from agent-neighborhood.md>

## Investment Scenarios
<paste content from agent-investment.md>

## Market Conditions
<paste content from agent-market.md>

## Recommendation
- **Suggested offer range:** $X – $Y
- **Action:** <Buy / Hold / Pass>
- **Verify before offering:**
  - [ ] All comps with a licensed agent / MLS
  - [ ] Rent estimate against actual local listings
  - [ ] Inspection-contingent items (roof, HVAC, foundation)
  - [ ] HOA financials and special assessments
  - [ ] Property tax reassessment risk

## Sources
<bulleted list of every URL the agents fetched>
```

4. **Clean up** — delete the per-agent files (`agent-*.md`) and `property_facts.json` once `PROPERTY-ANALYSIS.md` is written. Keep `composite_score.json` for the PDF skill.

---

## Done

Tell the user the file path and the headline score. Suggest:
> Run `/real-estate-report-pdf` to get a styled PDF version of this report.
