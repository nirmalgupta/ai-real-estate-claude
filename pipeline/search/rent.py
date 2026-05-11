"""Rent comp enrichment for the search CLI.

For every listing returned by `pipeline.search.redfin`, attach an
estimated monthly rent, gross-rent multiplier (GRM), and a rough cap-
rate. The user can opt out with `--no-rent`.

Strategy:
  - Per the project's open-source philosophy, the default experience
    must work with $0 of paid services. So rent enrichment runs even
    when HUD_API_KEY is absent — it just falls back to ACS tract median.
  - We fetch the rent benchmark ONCE per run (one HTTP), keyed to the
    *search center's* county / tract. All listings inherit that rent
    benchmark, with a per-listing sqft-based luxury scalar.
  - This is intentionally lower-fidelity than the full `pipeline.run`
    on a specific property — search is a scanning tool, full analysis
    is a per-property tool. For high-confidence numbers run a full
    analysis on shortlisted properties.

A listing's monthly rent is computed by bedroom count:
  - With HUD FMR: pick `fmr_<beds>br` (capped at 4BR; HUD doesn't go higher)
  - Fallback: `acs_median_gross_rent × bed_scalar × sqft_scalar`
    bed_scalar:    studio=0.6, 1=0.75, 2=1.0, 3=1.25, 4=1.5, 5+=1.75
    sqft_scalar:   1.5x if sqft > 3000, else 1.0x

Rough cap rate uses a 45% expense-ratio default (insurance, tax, repairs,
vacancy, management). That's a coarse landlord-side rule of thumb; the
full pipeline uses fact-derived expenses instead.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

EXPENSE_RATIO = 0.45   # standard SFR landlord rule of thumb

BED_SCALAR = {0: 0.6, 1: 0.75, 2: 1.0, 3: 1.25, 4: 1.5}


def _bed_scalar(beds: int | None) -> float:
    if beds is None:
        return 1.0
    if beds <= 0:
        return BED_SCALAR[0]
    if beds >= 4:
        # 5+ bed luxury bump
        return 1.75 if beds >= 5 else BED_SCALAR[4]
    return BED_SCALAR[beds]


@dataclass
class RentBenchmark:
    """Anchor values fetched once per search run."""
    source: str          # 'hud_fmr' | 'acs_median' | 'unavailable'
    fmr_by_bed: dict[int, int] | None   # beds -> $/mo (when source=hud_fmr)
    acs_median: int | None              # $/mo (when source=acs_median)
    note: str            # human-readable provenance for the CLI


def fetch_rent_benchmark(state_fips: str, county_fips: str,
                         tract_fips: str | None = None) -> RentBenchmark:
    """Pick the best rent anchor available for this search center.

    Prefers HUD FMR when HUD_API_KEY is set; falls back to ACS tract
    median; surfaces 'unavailable' with a clear note if neither works.
    """
    api_key = os.environ.get("HUD_API_KEY")
    full_county = f"{state_fips}{county_fips}"

    if api_key:
        fmr = _fetch_hud_fmr(full_county, api_key)
        if fmr:
            return RentBenchmark(
                source="hud_fmr",
                fmr_by_bed=fmr,
                acs_median=None,
                note=f"HUD FMR for county FIPS {full_county}",
            )

    # Fall back to ACS tract median
    if tract_fips:
        acs = _fetch_acs_median(state_fips, county_fips, tract_fips)
        if acs:
            return RentBenchmark(
                source="acs_median",
                fmr_by_bed=None,
                acs_median=acs,
                note=f"ACS 5-yr median gross rent for tract "
                     f"{state_fips}{county_fips}{tract_fips}"
                     + (" (set HUD_API_KEY for better fidelity)"
                        if not api_key else ""),
            )
    return RentBenchmark(
        source="unavailable",
        fmr_by_bed=None,
        acs_median=None,
        note="No rent benchmark available "
             "(set HUD_API_KEY or check ACS coverage)",
    )


def _fetch_hud_fmr(county_fips: str, api_key: str) -> dict[int, int] | None:
    """Return {0: studio, 1: 1br, ... 4: 4br} or None on failure."""
    from datetime import datetime

    url = f"https://www.huduser.gov/hudapi/public/fmr/data/{county_fips}"
    params = {"year": str(datetime.now().year - 1)}
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        r = httpx.get(url, params=params, headers=headers, timeout=30.0)
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError):
        return None

    body = data.get("data", data) or {}
    rec = body["basicdata"][0] if isinstance(body.get("basicdata"), list) else body
    if not isinstance(rec, dict):
        return None

    by_bed: dict[int, int] = {}
    keymap = {
        0: ("Efficiency", "efficiency"),
        1: ("One-Bedroom", "One Bedroom", "fmr_1"),
        2: ("Two-Bedroom", "Two Bedroom", "fmr_2"),
        3: ("Three-Bedroom", "Three Bedroom", "fmr_3"),
        4: ("Four-Bedroom", "Four Bedroom", "fmr_4"),
    }
    for beds, candidates in keymap.items():
        for k in candidates:
            v = rec.get(k)
            if v is None:
                continue
            try:
                by_bed[beds] = int(v)
                break
            except (TypeError, ValueError):
                continue
    return by_bed or None


def _fetch_acs_median(state_fips: str, county_fips: str,
                      tract_fips: str) -> int | None:
    """ACS 5-year B25064 (median gross rent) at tract level. Open API, no key."""
    url = "https://api.census.gov/data/2022/acs/acs5"
    params = {
        "get": "B25064_001E",
        "for": f"tract:{tract_fips}",
        "in": f"state:{state_fips} county:{county_fips}",
    }
    try:
        r = httpx.get(url, params=params, timeout=20.0)
        r.raise_for_status()
        rows = r.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not isinstance(rows, list) or len(rows) < 2:
        return None
    try:
        return int(rows[1][0])
    except (TypeError, ValueError, IndexError):
        return None


def estimate_rent(beds: int | None, sqft: int | None,
                  bench: RentBenchmark) -> tuple[int, str] | None:
    """Return (monthly_rent, source_label) or None if no anchor available."""
    if bench.source == "hud_fmr" and bench.fmr_by_bed:
        # Clamp beds to 0-4 for the lookup
        b = max(0, min(4, beds or 0))
        if b in bench.fmr_by_bed:
            rent = bench.fmr_by_bed[b]
            return rent, f"FMR-{b}br"

    if bench.source == "acs_median" and bench.acs_median:
        scalar = _bed_scalar(beds)
        if sqft and sqft > 3000:
            scalar *= 1.5
        return int(bench.acs_median * scalar), f"ACS×{scalar:.2f}"

    return None


def compute_rent_metrics(price: int | None, rent: int | None
                         ) -> tuple[float | None, float | None]:
    """Return (GRM, rough_cap_rate). Either may be None if inputs missing."""
    if not price or not rent or rent <= 0:
        return None, None
    annual_rent = rent * 12
    grm = price / annual_rent
    cap = (annual_rent * (1 - EXPENSE_RATIO)) / price
    return round(grm, 1), round(cap, 4)
