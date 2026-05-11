"""BEA Regional per-capita personal income by county.

Source: BEA Regional dataset, table CAINC1 (Personal income summary)
    https://apps.bea.gov/api/data/?...&datasetname=Regional&TableName=CAINC1&LineCode=3

Required: free API key from https://apps.bea.gov/api/signup/ as env
var `BEA_API_KEY`. Without the key, this source no-ops cleanly — the
end-to-end pipeline must still work with $0 of paid/registered services
(see open-source philosophy).

Returns: county per-capita personal income (latest year) plus 5-year
compound annual growth rate. Stronger 'neighborhood tier' signal than
ACS median household income because it includes investment income.
"""
from __future__ import annotations

import json
import os

import httpx

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult, Source

BEA_API = "https://apps.bea.gov/api/data/"
TABLE = "CAINC1"
LINE_CODE_PER_CAPITA = "3"


def _to_float(v) -> float | None:
    if v is None or v == "":
        return None
    # BEA returns numeric fields as strings, possibly with commas
    s = str(v).replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _cagr(start: float, end: float, years: int) -> float | None:
    if start <= 0 or years <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def _pick_series(rows: list[dict]) -> list[tuple[int, float]]:
    """From the BEA Data array, return [(year, value), ...] ascending by year,
    filtering out NA values that BEA encodes as '(NA)' / '(D)' / '(L)'."""
    series: list[tuple[int, float]] = []
    for row in rows:
        v = _to_float(row.get("DataValue"))
        y = row.get("TimePeriod")
        if v is None or not y:
            continue
        try:
            series.append((int(y), v))
        except ValueError:
            continue
    series.sort(key=lambda t: t[0])
    return series


class BeaRegionalSource(Source):
    name = "bea_regional"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("BEA_API_KEY")

    def fetch(self, address: Address) -> FetchResult:
        if not self.api_key:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error="BEA_API_KEY not set — skipping. Get a free key at "
                      "https://apps.bea.gov/api/signup/ if you want county "
                      "per-capita personal income added to analyses.",
            )

        county_fips = f"{address.state_fips}{address.county_fips}"
        params = {
            "UserID": self.api_key,
            "method": "GetData",
            "datasetname": "Regional",
            "TableName": TABLE,
            "LineCode": LINE_CODE_PER_CAPITA,
            "GeoFips": county_fips,
            "Year": "ALL",
            "ResultFormat": "JSON",
        }
        try:
            r = httpx.get(BEA_API, params=params, timeout=30.0)
            r.raise_for_status()
            payload = r.json()
        except (httpx.HTTPError, json.JSONDecodeError) as e:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"BEA Regional fetch failed: {e}",
            )

        results = payload.get("BEAAPI", {}).get("Results", {})
        # BEA wraps errors as Error objects either at the top level or
        # as Results: { Error: ... }
        if "Error" in results or "Error" in payload.get("BEAAPI", {}):
            err = results.get("Error") or payload["BEAAPI"]["Error"]
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"BEA Regional API error: {err}",
            )

        rows = results.get("Data", [])
        series = _pick_series(rows)
        if not series:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"BEA Regional returned no usable rows for county "
                      f"{county_fips}.",
            )

        latest_year, latest_val = series[-1]
        ref = f"{BEA_API}?TableName={TABLE}&LineCode={LINE_CODE_PER_CAPITA}&GeoFips={county_fips}"
        facts: dict[str, Fact] = {}

        def add(key: str, value, note: str | None = None) -> None:
            if value is None:
                return
            facts[key] = Fact(value=value, source=self.name, raw_ref=ref, note=note)

        add("county_per_capita_personal_income", int(latest_val),
            note=f"{latest_year} (BEA Regional CAINC1 LineCode 3)")
        add("county_per_capita_personal_income_year", latest_year)

        # 5-yr CAGR (or closest available span if fewer years returned)
        if len(series) >= 2:
            span = min(5, len(series) - 1)
            start_year, start_val = series[-(span + 1)]
            cagr = _cagr(start_val, latest_val, span)
            if cagr is not None:
                add("county_per_capita_personal_income_cagr",
                    round(cagr, 4),
                    note=f"{start_year}→{latest_year} ({span}-yr CAGR)")

        return FetchResult(
            source_name=self.name, address=address, facts=facts,
            raw={"county_fips": county_fips, "series_len": len(series)},
        )
