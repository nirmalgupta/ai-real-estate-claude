"""HUD Fair Market Rent — official rent benchmarks by metro/county.

Used by Section 8 voucher program. Considered the floor of "what the
government thinks market rent is for this area." Useful for sanity-
checking listing-aggregator rent estimates and for rural/secondary
markets where Zillow Rent Zestimate has thin data.

API: https://www.huduser.gov/hudapi/public/fmr/data/{entity}?year=YYYY
Requires a free API key from https://www.huduser.gov/hudapi/ — set as
HUD_API_KEY env var. Without it, this fetcher gracefully no-ops with a
clear error message so the rest of the pipeline still runs.

Entity ID format for county-level FMR is "METRO###M+CCCXX" (HUD's own
opaque scheme) but the API also accepts a 5-digit county FIPS code.
"""
from __future__ import annotations

import os
from datetime import datetime

import httpx

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult, Source

HUD_FMR_BASE = "https://www.huduser.gov/hudapi/public/fmr/data"


class HudFmrSource(Source):
    name = "hud_fmr"

    def fetch(self, address: Address) -> FetchResult:
        api_key = os.environ.get("HUD_API_KEY")
        if not api_key:
            return FetchResult(
                source_name=self.name,
                address=address,
                facts={},
                error=(
                    "HUD_API_KEY not set. Get a free key at "
                    "https://www.huduser.gov/hudapi/ and `export HUD_API_KEY=...`"
                ),
            )

        # Try previous fiscal year first — the current year's data isn't
        # always published until late in the year.
        year = datetime.now().year - 1
        county_fips = address.full_county_fips
        url = f"{HUD_FMR_BASE}/{county_fips}"
        params = {"year": str(year)}
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            r = httpx.get(url, params=params, headers=headers, timeout=30.0)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as e:
            return FetchResult(
                source_name=self.name,
                address=address,
                facts={},
                error=f"HUD FMR request failed: {e}",
            )

        # Response shape varies depending on whether the county has metro
        # subdivisions. Walk it defensively.
        body = data.get("data", data) or {}

        # When the county is a single FMR area, body has top-level keys
        # like "Efficiency", "One-Bedroom", etc. When it has subdivisions,
        # body["basicdata"] is a list of areas. Walk both shapes.
        candidates = []
        if isinstance(body, dict):
            if "basicdata" in body and isinstance(body["basicdata"], list):
                candidates = body["basicdata"]
            else:
                candidates = [body]
        elif isinstance(body, list):
            candidates = body

        if not candidates:
            return FetchResult(
                source_name=self.name,
                address=address,
                facts={},
                error=f"HUD FMR returned no data for county FIPS {county_fips}",
            )

        rec = candidates[0]   # First (or only) FMR area in the county

        ref = f"{url}?year={year}"

        def _maybe(label: str, key_options: list[str]) -> Fact | None:
            for k in key_options:
                v = rec.get(k)
                if v is not None:
                    try:
                        return Fact(value=int(v), source=self.name, raw_ref=ref)
                    except (TypeError, ValueError):
                        continue
            return None

        facts: dict[str, Fact] = {}
        # Field names in HUD's API have inconsistent casing across years
        # — check several aliases.
        for label, keys in [
            ("fmr_efficiency", ["Efficiency", "efficiency"]),
            ("fmr_1br", ["One-Bedroom", "One Bedroom", "fmr_1"]),
            ("fmr_2br", ["Two-Bedroom", "Two Bedroom", "fmr_2"]),
            ("fmr_3br", ["Three-Bedroom", "Three Bedroom", "fmr_3"]),
            ("fmr_4br", ["Four-Bedroom", "Four Bedroom", "fmr_4"]),
        ]:
            f = _maybe(label, keys)
            if f is not None:
                facts[label] = f

        if "year" not in facts and rec.get("year"):
            facts["fmr_year"] = Fact(value=rec["year"], source=self.name, raw_ref=ref)
        else:
            facts["fmr_year"] = Fact(value=year, source=self.name, raw_ref=ref)

        return FetchResult(
            source_name=self.name,
            address=address,
            facts=facts,
            raw=data,
        )
