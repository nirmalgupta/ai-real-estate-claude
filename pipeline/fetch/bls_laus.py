"""BLS Local Area Unemployment Statistics (LAUS).

For each property's county, fetch the latest monthly unemployment rate
plus the rate from 12 months earlier. Useful for the market section
(rising unemployment ⇒ softer rents, softer prices).

BLS series ID format for county LAUS unemployment rate:
    LAUCN<state2><county3>0000000003

Example for Denton County TX (48-121):
    LAUCN481210000000003

Public API: https://api.bls.gov/publicAPI/v2/timeseries/data/<seriesId>
No key required for the v2 unauthenticated tier (25 queries/day per IP,
which is plenty for our one-call-per-property pattern).

Response shape:
    { "Results": { "series": [
        { "seriesID": "...", "data": [
            { "year": "2026", "period": "M02", "value": "3.8", "latest": "true" },
            ...
        ]}
    ]}}

Data is returned newest-first. Months can have empty values (footnote
"X") — e.g., October 2025 during the lapse-in-appropriations gap. We
skip those when picking the latest.
"""
from __future__ import annotations

import json

import httpx

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult, Source

BLS_API = "https://api.bls.gov/publicAPI/v2/timeseries/data/{series}"
SERIES_PREFIX = "LAUCN"
SERIES_SUFFIX = "0000000003"  # measure code 03 = unemployment rate


def _series_id(state_fips: str, county_fips: str) -> str:
    return f"{SERIES_PREFIX}{state_fips}{county_fips}{SERIES_SUFFIX}"


def _parse_value(v: str | None) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _pick_latest_and_yoy(data: list[dict]) -> tuple[dict | None, dict | None]:
    """From a BLS data array (newest-first), return (latest_with_value,
    same_period_one_year_earlier). Either may be None."""
    priced = [d for d in data if _parse_value(d.get("value")) is not None]
    if not priced:
        return None, None
    latest = priced[0]
    target_year = str(int(latest["year"]) - 1)
    target_period = latest["period"]
    yoy = next(
        (d for d in priced
         if d.get("year") == target_year and d.get("period") == target_period),
        None,
    )
    return latest, yoy


class BlsLausSource(Source):
    name = "bls_laus"

    def fetch(self, address: Address) -> FetchResult:
        series = _series_id(address.state_fips, address.county_fips)
        url = BLS_API.format(series=series)
        try:
            r = httpx.get(url, timeout=30.0)
            r.raise_for_status()
            payload = r.json()
        except (httpx.HTTPError, json.JSONDecodeError) as e:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"BLS LAUS fetch failed: {e}",
            )

        if payload.get("status") != "REQUEST_SUCCEEDED":
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"BLS LAUS returned status={payload.get('status')}: "
                      f"{payload.get('message')}",
            )

        series_list = payload.get("Results", {}).get("series", [])
        if not series_list or not series_list[0].get("data"):
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"BLS LAUS returned no data for series {series}.",
            )

        data = series_list[0]["data"]
        latest, yoy = _pick_latest_and_yoy(data)
        if latest is None:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error="BLS LAUS data contained no non-empty values.",
            )

        latest_val = _parse_value(latest["value"])
        facts: dict[str, Fact] = {}
        ref = url

        def add(key: str, value, note: str | None = None) -> None:
            if value is None:
                return
            facts[key] = Fact(value=value, source=self.name, raw_ref=ref, note=note)

        add("county_unemployment_rate", latest_val,
            note=f"{latest['periodName']} {latest['year']} (BLS series "
                 f"{series}); preliminary if footnoted 'P'")
        add("county_unemployment_period",
            f"{latest['year']}-{latest['period']}")

        if yoy is not None:
            yoy_val = _parse_value(yoy["value"])
            if yoy_val is not None and latest_val is not None:
                add("county_unemployment_rate_yoy_pct_pts",
                    round(latest_val - yoy_val, 2),
                    note=f"vs {yoy['periodName']} {yoy['year']} ({yoy_val}%)")

        return FetchResult(
            source_name=self.name, address=address, facts=facts,
            raw={"series_id": series, "latest": latest, "yoy": yoy},
        )
