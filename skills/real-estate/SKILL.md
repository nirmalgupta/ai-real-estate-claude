---
name: real-estate
description: AI Real Estate Analyst v2 — pipeline-driven property audit. Deterministic Python data layer (FEMA flood, Census ACS, HUD FMR, NCES schools, NOAA storm history, USGS seismic, county CAD parcels, Movoto listing) feeds a wiki knowledge base; Claude reads the wiki + computed financial numbers and drafts each section. Trigger when the user runs /real-estate <address>, asks for a "full real estate analysis", or pastes a listing URL.
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

## Phase A — Run the data pipeline (deterministic, ~30–60 sec)

```
python3 -m pipeline.run "<full address>" --movoto-url "<url-if-known>"
```

Sources the pipeline hits per run:

| Source | What you get |
|---|---|
| Census Geocoder + Nominatim/FCC | lat/lon + state/county/tract FIPS |
| FEMA NFHL | official flood zone (X / AE / VE / etc) |
| Census ACS 5-year | tract demographics, median income/home value/rent, owner-occupancy %, education % |
| HUD FMR | gov fair-market rent (needs `HUD_API_KEY`) |
| NCES public schools | nearest 3 elementary / middle / high schools, with locale code, distance, NCES IDs |
| NOAA SPC storm CSVs | 10-yr counts of EF1+ tornadoes, hail ≥1.5", convective wind ≥58mph within 10mi |
| USGS NSHM | seismic PGA at 2%-in-50yr (ASCE 7 design-basis level) |
| County CAD adapter | tax-assessed value, market value, owner, year built, legal description, lot size, sale price + date *(disclosure states only)* — **runs only if a CAD adapter is registered for the county** |
| Movoto | list price, beds/baths/sqft/lot/year, photos, listing description |

Output: `wiki/properties/<slug>.md` with structured JSON frontmatter
plus a human-readable section. Every fact carries `source`,
`fetched_at`, and `raw_ref` for provenance.

If a fetcher fails (e.g., HUD without API key, Movoto search miss,
unsupported county), keep going — failures are reported per-source in
the wiki "Fetch errors" section and the rest of the pipeline still
produces a usable wiki page.

### County CAD coverage

Live ✅ in the registry: Denton, Dallas, Collin, Travis, Williamson,
Hays, Fort Bend, Montgomery, Brazoria, Galveston (TX); Miami-Dade,
Broward, Palm Beach (FL); Wake, Orange, Johnston (NC).

Registered but ⚠️ unsupported (no public REST endpoint identified):
Tarrant TX, Harris TX, Durham NC, Chatham NC. The pipeline still runs;
the CAD section will say `service_url not configured`.

If the property is in a county that has no adapter at all, note this
in the recommendation: "verify tax-assessed value and last sale via
county appraisal district directly."

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
| `1-snapshot.md` | Address, list price, beds/baths/sqft/lot/year, key features, DOM, price history. **Cross-check** list price against `tax_market_value` from the CAD if available — flag any > 30% gap. |
| `2-comps.md` | Use WebSearch for closed comps within ~1 mi, last 12 months. Compute $/sqft median + range, give an FMV estimate. Flag list-vs-FMV gap. |
| `3-rental.md` | Paste numbers from `computed.json`. Frame the verdict: positive/negative cash flow, key ratios, break-even points. **Note the tax-reassessment time bomb** if list price >> CAD `tax_assessed_value` (TX 10% homestead cap means new buyers reset to market). |
| `4-neighborhood.md` | **Schools first** — pull `nearest_elementary_schools` / `_middle_schools` / `_high_schools` from the wiki frontmatter. Each school carries name, distance, locale code, NCES ID, grade range. Add Census ACS demographics, walkability research, growth catalysts. |
| `5-risk.md` | FEMA flood zone (from wiki). **Storm history** — pull `storm_tornado_ef1plus_10yr_count`, `storm_hail_15in_plus_10yr_count`, `storm_wind_58mph_plus_10yr_count` from wiki and translate into insurance/roof-replacement implications (hail is the #1 driver of TX homeowner claims). **Seismic** — `seismic_pga_2pct_50yr` interpreted: <0.1g low, 0.1–0.3g moderate, >0.3g high. |
| `6-investment.md` | Buy-and-hold 7-yr (from `computed.json`), BRRRR feasibility, flip math. **Use CAD owner data** — if `owner_name` shows the same individual for 10+ years and the property is way under-improved vs. neighbors, that's a value-add candidate. |
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
- **Per-source data status** — which fetchers landed data, which failed (and why)

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
- **CAD partial coverage:** some adapters (Dallas, Travis, Montgomery)
  return parcel + owner only because their public REST layer doesn't
  expose appraisal values. The wiki frontmatter is the source of truth
  for what actually came back — don't assume a fact exists.
- **Tax reassessment risk (TX especially):** if `tax_assessed_value`
  is much lower than the list price, the new owner's first tax bill
  will reset close to market. Bake this into the rental and offer math.
- **NOAA SPC cache:** the storm-history fetcher caches per-year CSVs
  under `~/.cache/ai-real-estate-pipeline/spc/`. First run for a new
  year-window pulls ~3 MB; subsequent runs are local.
- **Where the schema/registry lives:** `pipeline/fetch/county/__init__.py`
  is the registry; `pipeline/fetch/county/_<state>_base.py` holds the
  TX/FL/NC defaults; `docs/data-sources.md` lists the supported
  counties with ✅/⚠️ status.
