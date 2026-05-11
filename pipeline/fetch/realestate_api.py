"""RealEstateAPI fallback for counties without a bespoke CAD adapter.

This is a *paid* backend. The pipeline calls it only when:
  1. The user opted in at install time (`apis.realestate.key` is set, or
     the `REALESTATE_API_KEY` env var is present), AND
  2. No bespoke CAD adapter is registered for the property's county
     (run.py only adds this fetcher in that branch).

Per the open-source / hobby philosophy: paid backends are quiet
enhancements, never required, never prompted at runtime.

API:
  POST https://api.realestateapi.com/v2/PropertyDetail
  Headers: x-api-key: <key>
  Body: {"address": str, "city": str, "state": str, "zip": str}

The response shape varies across plan tiers and the API has versioned
field renames. We extract conservatively, surfacing whichever common
aliases appear so the wiki layer gets the same standard fact keys it
gets from a bespoke CAD adapter (tax_assessed_value, etc.).
"""
from __future__ import annotations

from typing import Any

import httpx

from pipeline.common.address import Address
from pipeline.common.config import api_key
from pipeline.fetch.base import Fact, FetchResult, Source

ENDPOINT = "https://api.realestateapi.com/v2/PropertyDetail"


# Aliases to walk for each standard fact key. RealEstateAPI returns
# nested JSON; we accept either dotted paths or flat names. The walker
# below tolerates both shapes.
_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "tax_assessed_value": (
        "assessment.totalValue", "assessment.assessedValue",
        "assessor.totalValue", "assessedValue",
    ),
    "tax_market_value": (
        "assessment.marketTotalValue", "assessor.marketTotalValue",
        "marketTotalValue", "marketValue",
    ),
    "tax_appraised_value": (
        "assessment.appraisedValue", "assessor.appraisedValue",
        "appraisedValue",
    ),
    "owner_name": (
        "owner.name", "ownerName", "owner1FullName",
    ),
    "last_sale_price": (
        "lastSale.amount", "lastSale.price", "lastSalePrice",
    ),
    "last_sale_date": (
        "lastSale.date", "lastSaleDate",
    ),
    "year_built_cad": (
        "building.yearBuilt", "yearBuilt",
    ),
    "living_area_sqft_cad": (
        "building.livingArea", "building.totalLivingArea", "livingArea",
    ),
    "lot_size_sqft": (
        "lot.lotSquareFootage", "lotSquareFootage", "lotSizeSqFt",
    ),
    "legal_description": (
        "lot.legalDescription", "legalDescription",
    ),
    "apn": (
        "identifier.apn", "apn", "parcelNumber",
    ),
}


def _walk(obj: Any, path: str) -> Any:
    """Pull a possibly-nested value out of a JSON-ish dict via dotted path."""
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
        if cur is None:
            return None
    return cur


def _pick(obj: dict, aliases: tuple[str, ...]) -> Any:
    for path in aliases:
        v = _walk(obj, path)
        if v not in (None, "", []):
            return v
    return None


class RealEstateApiSource(Source):
    name = "realestate_api"

    def fetch(self, address: Address) -> FetchResult:
        key = api_key("realestate", env_var="REALESTATE_API_KEY")
        if not key:
            # Should never run when not configured — pipeline.run guards
            # against this. But be defensive.
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error="RealEstateAPI not configured — skipping.",
            )

        body = {
            "address": address.matched.split(",")[0].strip(),
            "city": address.city or "",
            "state": address.state_abbr or "",
            "zip": (address.zip or "")[:5],
        }
        headers = {"x-api-key": key, "Content-Type": "application/json"}

        try:
            r = httpx.post(ENDPOINT, json=body, headers=headers, timeout=30.0)
            if r.status_code in (401, 403):
                return FetchResult(
                    source_name=self.name, address=address, facts={},
                    error=f"RealEstateAPI auth failed ({r.status_code}). "
                          "Check apis.realestate.key in your config.",
                )
            r.raise_for_status()
            payload = r.json()
        except (httpx.HTTPError, ValueError) as e:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"RealEstateAPI fetch failed: {e}",
            )

        # Some plans return the property object at the top level; others
        # wrap it under "data" or "property"
        record = (
            payload.get("data") or payload.get("property")
            or (payload.get("results") or [None])[0] or payload
        )
        if not isinstance(record, dict):
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error="RealEstateAPI returned an unrecognized response shape.",
            )

        ref = f"{ENDPOINT} (key redacted)"
        facts: dict[str, Fact] = {}
        for std_key, aliases in _FIELD_ALIASES.items():
            v = _pick(record, aliases)
            if v in (None, "", []):
                continue
            facts[std_key] = Fact(
                value=v, source=self.name, raw_ref=ref,
                confidence="medium",
                note="RealEstateAPI fallback (no bespoke CAD adapter for "
                     f"{address.county_name} County, {address.state_abbr})",
            )

        if not facts:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error="RealEstateAPI response contained no recognizable fields. "
                      "Schema may have drifted; raise an issue with sample "
                      "payload to map new field names.",
            )

        return FetchResult(
            source_name=self.name, address=address, facts=facts,
            raw={"endpoint": ENDPOINT, "n_recognized_fields": len(facts)},
        )
