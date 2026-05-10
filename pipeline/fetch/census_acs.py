"""Census ACS 5-year — neighborhood demographics at the tract level.

Uses the Census Data API. Works without an API key for low volume
(<500 calls/day); set CENSUS_API_KEY env var for the higher 50,000/day tier.

Field cheat-sheet for ACS 5-year (variable codes documented in
the ACS Subject and Detailed Tables on api.census.gov):
    B19013_001E  median household income, past 12 months ($)
    B25077_001E  median home value (owner-occupied units, $)
    B25064_001E  median gross rent ($/mo)
    B25003_002E  owner-occupied housing units (count)
    B25003_001E  total occupied housing units (count) — for ownership %
    B15003_022E  bachelor's degree count (age 25+)
    B15003_001E  total population age 25+   — for education %
    B01003_001E  total population
"""
from __future__ import annotations

import os

import httpx

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult, Source

ACS_BASE = "https://api.census.gov/data/2022/acs/acs5"

VARIABLES = [
    "NAME",
    "B01003_001E",   # population
    "B19013_001E",   # median household income
    "B25077_001E",   # median home value
    "B25064_001E",   # median gross rent
    "B25003_001E",   # total occupied units
    "B25003_002E",   # owner-occupied units
    "B15003_001E",   # population 25+
    "B15003_022E",   # bachelor's count
]


def _to_int(s: str | None) -> int | None:
    if s in (None, "", "-666666666", "-888888888"):
        return None
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


class CensusACSSource(Source):
    name = "census_acs"

    def fetch(self, address: Address) -> FetchResult:
        params: dict[str, str] = {
            "get": ",".join(VARIABLES),
            "for": f"tract:{address.tract_fips}",
            "in": f"state:{address.state_fips} county:{address.county_fips}",
        }
        api_key = os.environ.get("CENSUS_API_KEY")
        if api_key:
            params["key"] = api_key

        try:
            r = httpx.get(ACS_BASE, params=params, timeout=30.0)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as e:
            return FetchResult(
                source_name=self.name,
                address=address,
                facts={},
                error=f"Census ACS request failed: {e}",
            )

        if not isinstance(data, list) or len(data) < 2:
            return FetchResult(
                source_name=self.name,
                address=address,
                facts={},
                error=f"Unexpected ACS response shape: {data!r}",
            )

        header, row = data[0], data[1]
        rec = dict(zip(header, row))

        pop = _to_int(rec.get("B01003_001E"))
        income = _to_int(rec.get("B19013_001E"))
        home_value = _to_int(rec.get("B25077_001E"))
        rent = _to_int(rec.get("B25064_001E"))
        occ_total = _to_int(rec.get("B25003_001E"))
        occ_owner = _to_int(rec.get("B25003_002E"))
        edu_total = _to_int(rec.get("B15003_001E"))
        edu_bach = _to_int(rec.get("B15003_022E"))

        owner_pct = (
            round(100 * occ_owner / occ_total, 1)
            if occ_total and occ_owner is not None
            else None
        )
        bachelor_pct = (
            round(100 * edu_bach / edu_total, 1)
            if edu_total and edu_bach is not None
            else None
        )

        ref = f"{ACS_BASE} (tract {address.full_tract_fips})"
        facts: dict[str, Fact] = {}

        def add(key: str, val):
            if val is not None:
                facts[key] = Fact(value=val, source=self.name, raw_ref=ref)

        add("tract_name", rec.get("NAME"))
        add("tract_population", pop)
        add("median_household_income", income)
        add("median_home_value", home_value)
        add("median_gross_rent", rent)
        add("owner_occupancy_pct", owner_pct)
        add("bachelor_or_higher_pct", bachelor_pct)

        return FetchResult(
            source_name=self.name,
            address=address,
            facts=facts,
            raw=data,
        )
