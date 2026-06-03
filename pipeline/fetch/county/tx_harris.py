"""Harris County, TX — HCAD.

FIPS 48201. Houston, Pasadena, Bellaire, Spring (south).

Public endpoint: the Harris County enterprise GIS publishes the current
HCAD parcel roll (tax year, owner, appraised/market value, land area,
legal description) as a fully public ArcGIS MapServer layer — no token,
spatial point queries supported:

    https://www.gis.hctx.net/arcgis/rest/services/HCAD/Parcels/MapServer/0

That layer carries value/owner/legal/lot but NOT year_built or living
area. Those live in a separate public HCAD snapshot (tax year 2021),
keyed by `PARCEL_ID == HCAD_NUM`:

    https://geohwp.houstontx.gov/arcgis/rest/services/03_BaseData_External/Parcels_Historic/FeatureServer/13

So this adapter does a second, attribute-keyed lookup after the primary
spatial query to backfill `year_built_cad` / `living_area_sqft_cad`. The
snapshot is from 2021 and only residential parcels carry these fields;
the enrichment is best-effort and silently skipped when unavailable.
"""
from __future__ import annotations

from typing import Any

import httpx

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult
from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


def _to_int(v: Any) -> int | None:
    """Coerce HCAD's string/float numerics to int; None on junk/empty."""
    if v in (None, "", " "):
        return None
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return None


def _parse_geohwp_attrs(attrs: dict[str, Any]) -> dict[str, int]:
    """Pull year_built / living-area facts from a geohwp 2021 feature.

    Returns only the keys that have plausible values — empty dict for
    commercial/vacant parcels where these fields are null or zero.
    """
    out: dict[str, int] = {}
    yb = _to_int(attrs.get("YEAR_BUILT"))
    if yb and yb > 1700:
        out["year_built_cad"] = yb
    # TOTIMPSQFT is numeric; IMPR_SQ_FT is its string twin. Prefer the
    # numeric, fall back to the string.
    la = _to_int(attrs.get("TOTIMPSQFT"))
    if la is None:
        la = _to_int(attrs.get("IMPR_SQ_FT"))
    if la and la > 0:
        out["living_area_sqft_cad"] = la
    return out


class HarrisTxCAD(TxParcelCAD):
    name = "tx_harris_cad"
    full_county_fips = "48201"
    county_label = "Harris County, TX"
    service_url = (
        "https://www.gis.hctx.net/arcgis/rest/services/"
        "HCAD/Parcels/MapServer/0"
    )

    # Secondary 2021 snapshot for year_built / living area (PARCEL_ID == HCAD_NUM).
    geohwp_url = (
        "https://geohwp.houstontx.gov/arcgis/rest/services/"
        "03_BaseData_External/Parcels_Historic/FeatureServer/13"
    )
    geohwp_note = "HCAD 2021 snapshot (geohwp Parcels_Historic)"

    attr_map = {
        "tax_assessed_value":  ["total_appraised_val", "tax_value"],
        "tax_market_value":    ["total_market_val"],
        "tax_assessed_year":   ["tax_year"],
        "lot_size_sqft":       ["land_sqft"],
        "lot_size_acres":      ["acreage_1"],
        "legal_description":   ["legal_dscr_1"],
        "owner_name":          ["owner_name_1"],
        "property_id":         ["HCAD_NUM", "acct_num"],
    }

    def _geohwp_lookup(self, hcad_num: str) -> tuple[dict[str, int], str]:
        """Best-effort year_built / living-area lookup by HCAD account.

        Returns (facts, query_url). Any failure yields ({}, url) so the
        primary result is never lost to a flaky secondary service.
        """
        url = f"{self.geohwp_url}/query"
        if not hcad_num or not hcad_num.isdigit():
            return {}, url
        params = {
            "f": "json",
            "where": f"PARCEL_ID='{hcad_num}'",
            "outFields": "YEAR_BUILT,IMPR_SQ_FT,TOTIMPSQFT",
            "returnGeometry": "false",
        }
        try:
            r = httpx.get(url, params=params, timeout=self.timeout_s)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError):
            return {}, url
        features = data.get("features") if isinstance(data, dict) else None
        if not features:
            return {}, url
        return _parse_geohwp_attrs(features[0].get("attributes") or {}), url

    def fetch(self, address: Address) -> FetchResult:
        result = super().fetch(address)
        if not result.ok:
            return result

        pid = result.facts.get("property_id")
        hcad_num = str(pid.value).strip() if pid is not None else ""
        extra, ref = self._geohwp_lookup(hcad_num)
        for key, value in extra.items():
            result.facts[key] = Fact(
                value=value, source=self.name, raw_ref=ref, note=self.geohwp_note,
            )
        return result


register("48201", HarrisTxCAD)
