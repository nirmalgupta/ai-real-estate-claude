# Data sources

Catalogue of public/government data sources available for any US property
address. Some are wired into the pipeline today; the rest are documented
here so future fetchers have a reading list.

Legend:
- ✅ implemented in `pipeline/fetch/`
- 🔧 available, not yet wired in
- 🚫 not national — per-county or paywalled

---

## National sources (work for any US address)

| Source | What it gives you | Auth | Status |
|---|---|---|---|
| **US Census Geocoder** | Free-form address → lat/lon + state/county/tract/block FIPS in one call. Mediocre uptime. | None | ✅ `pipeline.common.address` |
| **Nominatim** (OpenStreetMap) | Free-form address → lat/lon. 1 req/sec rate limit. | None (set User-Agent) | ✅ fallback in `pipeline.common.address` |
| **FCC Block API** | lat/lon → census FIPS codes. Fast, reliable. | None | ✅ fallback in `pipeline.common.address` |
| **Census ACS** (American Community Survey 5-year) | Tract-level demographics: median household income, owner-occupancy %, median home value, median gross rent, education, age. The gold standard for "what kind of neighborhood is this." | Optional free key (raises limit from 500 → 50K calls/day) | ✅ `pipeline.fetch.census_acs` |
| **FEMA NFHL** (National Flood Hazard Layer) | Official FEMA flood zone (X / AE / AH / VE etc) by lat/lon. Authoritative — this IS the source of truth for flood designation. | None | ✅ `pipeline.fetch.fema_nfhl` |
| **HUD Fair Market Rent** | Government's published rent benchmark by metro/county/bedroom count. Used by Section 8. Useful for rural/secondary markets where Zillow Rent Zestimate has thin data, and for sanity-checking listing aggregator rent estimates. | Free API key (`HUD_API_KEY` env var) | ✅ `pipeline.fetch.hud_fmr` |
| **HUD CHAS** (Comprehensive Housing Affordability Strategy) | Housing cost burden, affordability by income tier. | None | 🔧 |
| **FEMA NFIP claims** | Historical flood insurance claims by ZIP. Better proxy for "does this area actually flood" than the static flood zone. | None | 🔧 |
| **NCES public schools** (Common Core of Data) | Every public school: enrollment, demographics, locale code. Note: ratings (GreatSchools/Niche) are paid; raw stats are free. | None | ✅ `pipeline.fetch.nces` |
| **USGS Earthquake Hazard** | Probabilistic seismic risk by lat/lon. National Seismic Hazard Map. | None | 🔧 |
| **NOAA Climate Normals** | 30-year temp/precip averages by station; useful for climate context. | None | 🔧 |
| **NOAA SPC** (Storm Prediction Center) | Tornado/hail/wind reports historical archive. | None | 🔧 |
| **EPA EJScreen** | Environmental justice screening: pollution exposure by tract. | None | 🔧 |
| **EPA Superfund** (CERCLIS) | Active and historical Superfund sites by location. | None | 🔧 |
| **BLS LAUS** (Local Area Unemployment Statistics) | Unemployment rate by county. | None | 🔧 |
| **BEA Regional** | Per-capita personal income by MSA/county. | Free key | 🔧 |
| **DOT AADT** (Annual Average Daily Traffic) | Traffic counts by road segment — useful for "is this on a busy road" assessment. | None | 🔧 |

---

## Listing aggregators (for property-specific facts)

| Source | What it gives you | Status | Notes |
|---|---|---|---|
| **Movoto** | List price, beds/baths, sqft, lot, year built, photos, listing description. | ✅ `pipeline.fetch.movoto` | Direct URL works; their search API is JS-rendered and 404s plain HTTP. Use `--movoto-url` override. |
| **Zillow** | Zestimate + listing data. | 🚫 | Aggressive anti-bot. Returns 403 to plain HTTP. Would need Playwright + stealth or a paid API. |
| **Redfin** | Redfin Estimate + listing data. | 🚫 | Same as Zillow. |
| **Realtor.com** | MLS-fed listings. | 🚫 | Same. Cloudflare-protected. |
| **HAR.com** | Houston-area MLS feed. | 🚫 | 403s plain HTTP. |
| **Compass** | High-end listings; needs login for full details. | 🚫 | Requires authenticated session. |

---

## Property-specific data — NOT national, plug-in per-county

Property assessment is a county function. There are 3,143 counties in
the US using ~30+ different CAD software platforms (TylerTech / PACS /
Patriot / iAS World / various custom in-house portals). No common
schema, no national index.

| What you want | Where it lives | Approach |
|---|---|---|
| **Tax-assessed value** | County Central Appraisal District | Per-county scraper. Registry: `pipeline/fetch/county/`. |
| **Last sale price + date** | County deed records | Same — scraped from each county's portal. |
| **Owner of record** | County deed records | Same. Public in most states. |
| **Lot legal description** | County plat / CAD records | Same. |
| **Permits / construction history** | City or county building dept | Per-municipality. Often only available via PRA request. |
| **HOA records** | Mostly nowhere public | Listing copy or seller disclosure. |
| **Recent comparable sales (closed)** | MLS (gold standard) or aggregator scrape | Paid: Bridge Interactive, RealEstateAPI, ATTOM. Free: scrape Movoto/Compass listing pages. |

The CAD registry is plug-in: see `pipeline/fetch/county/__init__.py`.
Adding an adapter is a 200–500-line per-county project.

Implemented adapters:

| County (FIPS) | Module | Sale price disclosed? |
|---|---|---|
| Denton, TX (48121) | `pipeline.fetch.county.tx_denton` | No (TX non-disclosure) |

---

## Paid alternatives (when public data isn't enough)

| Provider | What you get | Rough cost | When to consider |
|---|---|---|---|
| **RealEstateAPI** | Property-level data including tax assessor, ownership, comps. National. | ~$0.05–0.10 / property | Production tool serving real customers. |
| **ATTOM** | Comprehensive property data + analytics. | ~$500–2,000 / month | Commercial product. |
| **Bridge Interactive** | MLS feed access (requires real estate license affiliation). | ~$100–1,000 / month | Need real-time MLS data. |
| **GreatSchools API** | School ratings (1–10), reviews, test scores. | Free tier exists; manual approval | Want polished school ratings beyond raw NCES stats. |
| **CoreLogic** | AVMs, comps, climate risk. | Enterprise | Lender-tier accuracy. |
| **First Street Foundation** | Flood / fire / heat / wind risk scores (Risk Factor / FloodFactor). | Tiered API | Want forward-looking climate risk, not just FEMA's static zones. |

---

## Adding a new fetcher

1. Pick a source from the 🔧 list above (or a new one not listed).
2. Subclass `pipeline.fetch.base.Source`, implement `fetch(address) → FetchResult`.
3. Register the new source in `pipeline/run.py`'s `sources` list.
4. Each fact you produce should be a `Fact(value, source, raw_ref, confidence, note)`
   — provenance is the key invariant.

Suggested next four fetchers, in rough priority order:

1. **NCES schools** — pairs with `bachelor_or_higher_pct` from ACS to give a real schools picture. EDGE locale codes also tell you suburb vs urban vs rural.
2. **NOAA Climate Normals** — quick to add and feeds the risk section.
3. **USGS Earthquake** — same; one API call by lat/lon.
4. **FEMA NFIP claims** — historical flood evidence, complements the static flood zone.

After that, the meaningful next jump in usefulness is a **county CAD adapter** for whatever county you analyze most often (see `pipeline/fetch/county/`).
