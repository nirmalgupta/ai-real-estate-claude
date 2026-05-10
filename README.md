# AI Real Estate Analyst (v2 — pipeline-driven)

Investment-grade audit of a US property in ~2 minutes. **Deterministic
Python data layer** (FEMA flood, Census ACS, HUD FMR, Movoto listing,
plug-in county CADs) feeds a **wiki knowledge base**. Claude reads the
wiki + computed financial numbers and drafts each section. Final
report stitches into a single markdown + PDF.

Runs entirely under your **Claude Code subscription** — no API keys, no
per-token billing. Python does the boring deterministic work; the LLM
only does what only the LLM can do.

> ⚠️ This is the `pipeline-redesign` branch. v1 (Claude-orchestrated,
> 5-parallel-subagent design) lives on `main`. The two coexist; pick
> the branch you want before running `./install.sh`.

## What's different in v2

| | v1 (`main`) | v2 (this branch) |
|---|---|---|
| Data fetching | Claude's `WebFetch` (Zillow/Redfin frequently 403) | Python `httpx` w/ realistic headers + authoritative gov APIs |
| Data sources | Listing aggregators only | **FEMA NFHL** (flood), **Census ACS** (demographics), **HUD FMR** (rent benchmark), **Movoto** (listing), plug-in county CAD adapters |
| Geocoding | Implicit | **Census Geocoder + FCC fallback** → lat/lon + FIPS codes |
| Math | Done in-prompt by the LLM | Deterministic Python (`pipeline.analyze.finance`) — same inputs always produce same outputs |
| Knowledge persistence | None | **Wiki knowledge base** (`wiki/properties/<slug>.md`) with per-fact provenance: source, fetched_at, raw_ref |
| Subagents | 5 parallel via Claude `Task` | **None** — single-session orchestration; section drafting is sequential but cheap |
| Provenance | Best-effort URLs in the report | Every fact carries `{source, fetched_at, raw_ref, confidence}` |

## Install

```bash
git clone <repo-url> ai-real-estate-claude
cd ai-real-estate-claude
git checkout pipeline-redesign
./install.sh
```

`install.sh` ensures Python deps (`httpx`, `reportlab`) and copies
`skills/real-estate/` into `~/.claude/skills/`. It also offers to set
up your iMessage handle and reminds you to grab a free HUD API key.

## Use

```
> /real-estate 31 Glenleigh Pl, Spring, TX 77381
```

The skill walks Claude through six phases:

```
A. Fetch       python -m pipeline.run "<addr>" [--movoto-url <url>]
              → wiki/properties/<slug>.md  (FEMA + ACS + HUD + Movoto)

B. Extract     Read wiki/raw/<slug>.movoto.html, pull richer fields
              the regex layer missed (HOA, days on market, features,
              price history). Append to wiki frontmatter.

C. Compute     python -m pipeline.analyze.compute "<slug>" \
                   --rate <r> --rent <r> --tax <t> --insurance <i> ...
              → reports/<slug>/computed.json
                 (cash flow, cap rate, cash-on-cash, 7-yr CAGR,
                  break-even rent, break-even purchase price)

D. Draft       Claude writes 8 sections in-conversation, each as a
              file in reports/<slug>/sections/:
                1-snapshot · 2-comps · 3-rental · 4-neighborhood
                5-risk · 6-investment · 7-market · 8-recommendation

E. Synthesize  python -m pipeline.synthesize "<slug>"
              → reports/<slug>/PROPERTY-ANALYSIS.md
                 reports/<slug>/composite_score.json

F. Distribute  python ~/.claude/scripts/generate_pdf_report.py ...
              python ~/.claude/scripts/send_imessage.py ...   (optional)
```

## Run the data layer alone (no Claude Code needed)

The pipeline's deterministic phases (A, C, E) are pure Python — they
run from any shell, no LLM required.

```
$ python3 -m pipeline.run "31 Glenleigh Pl, Spring, TX 77381" \
    --movoto-url "https://www.movoto.com/the-woodlands-tx/31-glenleigh-pl-the-woodlands-tx-77381-403_39112602/"
[1/3] Geocoding: 31 Glenleigh Pl, Spring, TX 77381
      matched: 31 GLENLEIGH PL, SPRING, TX, 77381
      tract:   48339691301  (Montgomery County, TX)
[2/3] Fetching sources...
      - fema_nfhl... ok (2 fact(s))
      - census_acs... ok (7 fact(s))
      - hud_fmr...   FAILED: HUD_API_KEY not set
      - movoto...    ok (8 fact(s))
[3/3] Wrote wiki/properties/31-glenleigh-pl-spring-tx-77381.md

$ python3 -m pipeline.analyze.compute "31-glenleigh-pl-spring-tx-77381" \
    --rate 0.0675 --rent 8500 --tax 17964 --insurance 6500 --pool-monthly 200
  list price:           $   1,555,000
  est. monthly rent:    $       8,500
  monthly cash flow:    $      -5,026
  cap rate:                     2.35%
  break-even rent:      $      14,413
  break-even price:     $     800,357
  7-yr CAGR (approx):            2.20%
```

## Architecture

```
ai-real-estate-claude/
├── pipeline/
│   ├── common/address.py          ← Census Geocoder + Nominatim/FCC fallback
│   ├── fetch/
│   │   ├── base.py                ← Source ABC + Fact dataclass
│   │   ├── fema_nfhl.py           ← FEMA flood zone (lat/lon)
│   │   ├── census_acs.py          ← Tract-level demographics
│   │   ├── hud_fmr.py             ← Fair Market Rent benchmark
│   │   ├── movoto.py              ← Listing scraper
│   │   └── county/                ← Plug-in CAD registry
│   │       ├── __init__.py        ← register / get_cad_source
│   │       └── _adapters.py       ← Add `import` lines per county
│   ├── wiki/builder.py            ← First-source-wins merge → markdown wiki
│   ├── analyze/
│   │   ├── finance.py             ← Mortgage / cash flow / IRR / break-even
│   │   ├── compute.py             ← CLI: wiki facts → computed.json
│   │   └── wiki_loader.py         ← Parse wiki page back to facts dict
│   ├── run.py                     ← CLI: address → wiki page
│   └── synthesize.py              ← CLI: drafts → PROPERTY-ANALYSIS.md
├── skills/real-estate/SKILL.md    ← Orchestrator (Claude Code skill)
├── scripts/
│   ├── generate_pdf_report.py     ← Markdown → styled PDF
│   └── send_imessage.py           ← Send PDF via Messages.app
├── tests/
│   ├── test_finance.py
│   └── test_address.py
├── wiki/                          ← Knowledge base (gitignored)
├── reports/                       ← Per-property outputs (gitignored)
├── install.sh / uninstall.sh
└── requirements.txt               ← httpx, reportlab
```

## Adding a new county CAD adapter

1. Write `pipeline/fetch/county/<state>_<name>.py`:
   ```python
   from pipeline.fetch.county import CountyCADSource, register
   from pipeline.fetch.base import Fact, FetchResult

   class MontgomeryTxCAD(CountyCADSource):
       name = "tx_montgomery_cad"
       full_county_fips = "48339"
       county_label = "Montgomery County, TX"

       def fetch(self, address):
           # ... hit the county portal, parse, return FetchResult
           ...

   register("48339", MontgomeryTxCAD)
   ```
2. Add `from pipeline.fetch.county import <module>` to `_adapters.py`.
3. Run the pipeline; the new adapter is picked up automatically.

## Tests

```bash
python3 -m unittest tests.test_finance tests.test_address -v
```

## Composite score

Heuristic 0–100 weighted blend (in `pipeline/synthesize.py`):

| Dimension | Weight | What it measures |
|---|---|---|
| Cash flow | 30% | Going-in cap rate |
| Appreciation | 20% | 7-yr CAGR with assumed appreciation rate |
| Affordability | 30% | List price vs Census tract median home value |
| Flood | 20% | FEMA zone (X = best, V/AE = worst) |

Grades: A+ ≥90 · A ≥80 · B ≥65 · C ≥50 · D ≥35 · F <35
Signals: Strong Buy / Buy / Hold / Watch / Avoid

## Data sources

Wired-in today: **Census Geocoder** (with Nominatim+FCC fallback), **FEMA NFHL** (flood), **Census ACS** (tract demographics), **HUD FMR** (rent benchmark), **Movoto** (listing).

Available but not yet wired in: HUD CHAS, FEMA NFIP claims, NCES schools, USGS earthquake, NOAA climate normals, EPA EJScreen / Superfund, BLS unemployment, BEA income, DOT traffic counts.

Per-county / paid: tax-assessed value, last sale, owner of record, MLS comps. See [`docs/data-sources.md`](docs/data-sources.md) for the full catalogue, status of each source, paid alternatives, and a how-to-add-a-fetcher checklist.

## Limitations

- **Listing data is one source (Movoto)** — Zillow/Redfin/HAR/Realtor
  block plain HTTP. Add Playwright + stealth plugins if you need them.
- **Movoto search is unreliable.** Pass `--movoto-url` (find via
  Google `site:movoto.com "<address>"`) for reliable results.
- **No paid data.** No MLS, no ATTOM, no CoreLogic, no GreatSchools.
  We use only free public/government data + one listing aggregator.
- **County records are plug-in.** No adapters out of the box. Each
  county's CAD portal has a different schema; adapters are written
  per-county as needed.
- **AI-generated estimates.** Not financial or investment advice.
  Always verify with a licensed real estate professional before
  making decisions.

## License

MIT
