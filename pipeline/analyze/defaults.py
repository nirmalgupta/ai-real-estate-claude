"""Smart defaults for analyze.compute inputs.

When the user runs `python -m pipeline.analyze.compute <slug>` without
--rate / --tax / --insurance / --rent, derive each from the facts we
already have in the wiki page. Each function returns (value, source_label)
so compute.py can surface in the output where each number came from.

Free data only — no paid APIs. Mortgage rate uses Freddie Mac's public
PMMS history CSV; everything else reads facts already on disk.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import httpx

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "ai-real-estate-pipeline" / "pmms"

# Effective property tax rate by state, 2024 ATTOM / Tax Foundation
# composite (state + local average). For TX we bump slightly to reflect
# ISD-heavy effective rates in major metros like Frisco/Plano/Houston.
# Users in low-rate counties can override with --tax.
STATE_TAX_RATE = {
    "AL": 0.41, "AK": 1.19, "AZ": 0.62, "AR": 0.62, "CA": 0.75, "CO": 0.55,
    "CT": 2.15, "DE": 0.61, "DC": 0.62, "FL": 0.91, "GA": 0.92, "HI": 0.28,
    "ID": 0.69, "IL": 2.27, "IN": 0.84, "IA": 1.57, "KS": 1.41, "KY": 0.86,
    "LA": 0.55, "ME": 1.36, "MD": 1.05, "MA": 1.20, "MI": 1.62, "MN": 1.12,
    "MS": 0.81, "MO": 0.97, "MT": 0.83, "NE": 1.73, "NV": 0.59, "NH": 2.18,
    "NJ": 2.49, "NM": 0.80, "NY": 1.73, "NC": 0.84, "ND": 0.98, "OH": 1.56,
    "OK": 0.90, "OR": 0.93, "PA": 1.58, "RI": 1.63, "SC": 0.57, "SD": 1.31,
    "TN": 0.71, "TX": 1.90, "UT": 0.66, "VT": 1.90, "VA": 0.82, "WA": 0.98,
    "WV": 0.58, "WI": 1.85, "WY": 0.61,
}

# FRED's MORTGAGE30US series is the same Freddie Mac PMMS data Freddie
# publishes weekly, mirrored as CSV by the St. Louis Fed (Freddie's own
# CSV download was decommissioned in 2025 — they only ship XLSX now).
PMMS_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"
PMMS_CACHE_TTL = 24 * 3600  # one day


def _high_risk_flood(zone: str | None) -> bool:
    """SFHA zones (Special Flood Hazard Areas) — AE, VE, AO, AH, A, V."""
    if not zone:
        return False
    z = str(zone).upper().strip()
    return z in {"A", "AE", "AH", "AO", "AR", "V", "VE"} or z.startswith("A")


def default_rent(facts: dict, beds: int | None = None) -> tuple[float, str]:
    """Pick a monthly rent default.

    Priority:
      1. HUD FMR for the matching bedroom bucket (most defensible)
      2. ACS tract median gross rent (×1.5–2.5 luxury scaling)
      3. Zero (caller will see source label and know to investigate)
    """
    bed_to_key = {
        0: "fmr_efficiency",
        1: "fmr_1br",
        2: "fmr_2br",
        3: "fmr_3br",
        4: "fmr_4br",
        5: "fmr_4br",   # HUD caps at 4BR; use 4BR for 5+
    }
    if beds is not None and beds in bed_to_key:
        fmr = facts.get(bed_to_key[beds])
        if fmr:
            return float(fmr), f"HUD FMR ({bed_to_key[beds]})"

    acs = facts.get("median_gross_rent")
    sqft = facts.get("sqft", 0) or 0
    if acs:
        # Luxury scaling for outsized homes (same heuristic compute.py used)
        if sqft and sqft > 3000:
            return float(acs) * 2.5, "ACS median × 2.5 (luxury sqft)"
        return float(acs), "ACS tract median"
    return 0.0, "no rent fact available — pass --rent"


def default_tax(facts: dict, list_price: float, state: str | None
                ) -> tuple[float, str]:
    """Pick an annual property-tax default.

    Priority:
      1. CAD tax_assessed_value × state effective rate (most accurate)
      2. list_price × state effective rate
      3. list_price × 2% (legacy fallback)
    """
    rate_pct = STATE_TAX_RATE.get((state or "").upper(), 2.0)
    rate = rate_pct / 100.0

    assessed = facts.get("tax_assessed_value") or facts.get("tax_market_value")
    if assessed:
        return float(assessed) * rate, (
            f"CAD assessed value × {rate_pct:.2f}% state effective rate ({state})"
        )
    return list_price * rate, f"list_price × {rate_pct:.2f}% state effective rate ({state})"


def default_insurance(facts: dict, list_price: float) -> tuple[float, str]:
    """Pick an annual insurance default.

    Base 0.4% of list price, with bumps for documented risk:
      +0.4%   in SFHA flood zone (AE/VE/etc)
      +0.2%   high hail history (>3 ≥1.5" events in 10yr, 10mi radius)
      +0.2%   any NFIP claim activity (>5 claims in ZIP / 10yr)
    """
    rate = 0.004
    notes: list[str] = []

    if _high_risk_flood(facts.get("flood_zone")):
        rate += 0.004
        notes.append(f"+0.4% SFHA flood zone ({facts['flood_zone']})")

    hail = facts.get("hail_within_10mi_10yr") or 0
    if hail and hail > 3:
        rate += 0.002
        notes.append(f"+0.2% hail history ({hail} events/10yr)")

    nfip = facts.get("nfip_claims_count_10yr") or 0
    if nfip and nfip > 5:
        rate += 0.002
        notes.append(f"+0.2% NFIP claim activity ({nfip} claims in ZIP)")

    base_note = f"list_price × {rate*100:.2f}%"
    src = base_note + (" (" + "; ".join(notes) + ")" if notes else "")
    return list_price * rate, src


def default_mortgage_rate(cache_dir: Path = DEFAULT_CACHE_DIR
                          ) -> tuple[float, str]:
    """Latest weekly 30-yr fixed from Freddie Mac PMMS.

    Cached for 24h. Returns (rate as decimal, source label). Falls back
    to 0.065 if the fetch fails — the user will see the source label
    and know to pass --rate.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "pmms_30yr.csv"

    fresh = (
        cache_path.exists()
        and (time.time() - cache_path.stat().st_mtime) < PMMS_CACHE_TTL
    )
    body: str | None = None
    if fresh:
        try:
            body = cache_path.read_text()
        except OSError:
            body = None

    if body is None:
        try:
            r = httpx.get(PMMS_URL, timeout=30.0, follow_redirects=True)
            r.raise_for_status()
            body = r.text
            cache_path.write_text(body)
        except (httpx.HTTPError, OSError):
            return 0.065, "fallback (PMMS fetch failed; pass --rate)"

    latest = _parse_pmms_latest(body)
    if latest is None:
        return 0.065, "fallback (PMMS parse failed; pass --rate)"
    rate, week = latest
    return rate / 100.0, f"Freddie Mac PMMS 30-yr fixed, week of {week}"


def _parse_pmms_latest(csv_text: str) -> tuple[float, str] | None:
    """Pull the most recent (date, rate) from the PMMS history CSV.

    PMMS format has shifted across decades. We look for the last row
    whose first column parses as a date and whose second column parses
    as a number in a sane mortgage-rate range (1.0–25.0).
    """
    last: tuple[float, str] | None = None
    for line in csv_text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        date_str, rate_str = parts[0], parts[1]
        try:
            rate = float(rate_str)
        except ValueError:
            continue
        if not (1.0 <= rate <= 25.0):
            continue
        # Tolerate either MM/DD/YYYY or YYYY-MM-DD
        parsed = None
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
            try:
                parsed = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            continue
        last = (rate, parsed.strftime("%Y-%m-%d"))
    return last
