---
name: real-estate
description: AI Real Estate Analyst v2 — pipeline-driven property audit. Deterministic Python data layer (FEMA flood, Census ACS, HUD FMR, Movoto listing) feeds a wiki knowledge base; Claude reads the wiki + computed financial numbers and drafts each section. Trigger when the user runs /real-estate <address>, asks for a "full real estate analysis", or pastes a listing URL.
---

# Real Estate — v2 pipeline-driven analysis

End-to-end audit of one property. The Python pipeline does the boring,
deterministic work (HTTP, parsing, math); you (Claude) do the
judgment-heavy work (extraction, narrative, synthesis).

## Inputs

The user provides a US address (or a listing URL). Normalize to:
`123 Main St, City, ST 12345`.

If the user pasted a Movoto URL, capture it — you'll pass it as
`--movoto-url`. Otherwise try to find one via WebSearch:
`site:movoto.com "<address>"`. If that fails, the Movoto fetcher will
no-op and the analysis runs without listing data.

---

## Phase A — Run the data pipeline (deterministic, ~30 sec)

```
python3 -m pipeline.run "<full address>" --movoto-url "<url-if-known>"
```

Output: `wiki/properties/<slug>.md` with structured JSON frontmatter
plus a human-readable section. Every fact carries `source`,
`fetched_at`, and `raw_ref` for provenance.

If a fetcher fails (e.g., HUD without API key, Movoto search miss),
keep going — failures are reported per-source and the rest of the
pipeline still produces a usable wiki page.

---

## Phase B — Extract richer fields from raw listing HTML (optional)

If `wiki/raw/<slug>.movoto.html` exists (Movoto succeeded), open it
and extract any fields the regex layer missed: HOA, days on market,
features (pool, view, garage, finished basement), price history,
school assignments, listing agent narrative. Append the new facts to
the wiki page's frontmatter as `manual_extract: {...}`.

---

## Phase C — Compute financial numbers (deterministic, instant)

```
python3 -m pipeline.analyze.compute "<slug>" \\
    --rate <current 30-yr fixed rate> \\
    --rent <estimated monthly rent> \\
    --tax <annual property tax> \\
    --insurance <annual> \\
    --hoa-monthly <amount> \\
    --pool-monthly <if pool>
```

If the user didn't tell you the current mortgage rate, use WebSearch
to find today's 30-yr fixed (Freddie Mac PMMS, Bankrate, Mortgage News
Daily). Default the other inputs from listing facts where possible
(tax from listing, insurance defaults to 0.4% of list price).

Output: `reports/<slug>/computed.json` with cash flow, cap rate, GRM,
cash-on-cash, break-even rent, break-even purchase price, and 7-year
buy-and-hold projection.

---

## Phase D — Draft sections (you do this in-conversation)

Read both the wiki page and `computed.json`. Then write each section
as `reports/<slug>/sections/<n>.md`:

| File | What it contains |
|---|---|
| `1-snapshot.md` | Address, list price, beds/baths/sqft/lot/year, key features, DOM, price history |
| `2-comps.md` | Use WebSearch for closed comps within ~1 mi, last 12 months. Compute $/sqft median + range, give an FMV estimate. Flag list-vs-FMV gap. |
| `3-rental.md` | Paste numbers from `computed.json`. Frame the verdict: positive/negative cash flow, key ratios, break-even points. Note the tax-reassessment time bomb if list >> assessed. |
| `4-neighborhood.md` | Schools (research via WebSearch — Conroe ISD, GreatSchools etc), Census ACS demographics from wiki, walkability, growth catalysts. |
| `5-risk.md` | FEMA flood zone (from wiki), insurance implications, climate/hurricane risk for the region. |
| `6-investment.md` | Buy-and-hold 7-yr (from `computed.json`), BRRRR feasibility (turnkey vs. distressed?), flip math (break-even price for 15% margin). |
| `7-market.md` | Current submarket conditions: DOM, inventory, price trend YoY. Use WebSearch on Redfin/HAR/Realtor neighborhood pages. |
| `8-recommendation.md` | Suggested offer range, action (Buy/Hold/Pass), walk-away ceilings (owner-occupant vs. investor), verify-before-offering checklist. |

Keep each section to ~250–400 words. Tables welcome where they help.

---

## Phase E — Stitch the report (deterministic)

```
python3 -m pipeline.synthesize "<slug>"
```

Reads all `reports/<slug>/sections/*.md`, computes the composite score
from the data, prepends the score dashboard + executive summary, and
writes `reports/<slug>/PROPERTY-ANALYSIS.md`.

---

## Phase F — PDF + delivery (optional)

```
python3 ~/.claude/scripts/generate_pdf_report.py reports/<slug>/PROPERTY-ANALYSIS.md
```

If the user has set up an iMessage handle:
```
python3 ~/.claude/scripts/send_imessage.py <pdf-path> "<one-line summary>"
```

---

## Done

Tell the user:
- Path to the wiki page (`wiki/properties/<slug>.md`)
- Path to the report (`reports/<slug>/PROPERTY-ANALYSIS.md`)
- Path to the PDF (if generated)
- Headline score + grade + signal
- One-line action recommendation

## Notes

- **Where errors land:** if a fetcher fails, the wiki page logs it in
  the "Fetch errors" section. Mention any failures in your final
  summary so the user knows what wasn't included.
- **Movoto blocks:** if Movoto returns 401/403/429, ask the user to
  paste the listing URL manually (find via Google
  `site:movoto.com "<address>"`).
- **HUD API key:** rent benchmarks are a "nice to have." If
  `HUD_API_KEY` isn't set, skip and use the listing aggregator's rent
  estimate or your own research instead.
- **County records:** the CAD registry has no adapters yet
  (`pipeline/fetch/county/_adapters.py`). When you analyze a property
  in a new county, note in the recommendation: "verify tax-assessed
  value and last sale via county appraisal district."
