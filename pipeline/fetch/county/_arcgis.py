"""Reusable ArcGIS REST parcel base class.

Most county GIS offices publish a parcel feature service over ArcGIS
Server. The shape is consistent: a `MapServer/<layer>/query` endpoint
that accepts spatial filters and returns features whose attributes
contain the parcel's property fields (assessed value, owner, lot size,
legal description, etc).

The wrinkles that vary across counties:
- Layer URL and layer index.
- Which attribute key holds each piece of data — counties name these
  with no consistency. ASSESSED, MARKET_VALUE, TOTAL_APPR, etc all
  map to "assessed value" depending on the county.
- Whether the service exposes geometry, owner names, sale price.

This base does the HTTP and provenance plumbing. Subclasses set the
service URL and an attribute map that names how to pull each `Fact`
out of the raw feature attributes.

Subclass contract:
    full_county_fips = "48121"        # required
    county_label     = "Denton County, TX"
    service_url      = "https://.../FeatureServer/0"  # full URL incl. layer
    attr_map         = {
        "tax_assessed_value": ["TOTAL_APPRAISED_VAL", "ASSESSED"],
        "lot_size_sqft":      ["LAND_SQFT"],
        ...
    }
    sale_price_disclosed = False     # TX = False; FL/NC = True
"""
from __future__ import annotations

from typing import Any

import httpx

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult
from pipeline.fetch.county import CountyCADSource


# The standard Fact keys every CAD adapter populates when data exists.
# Subclasses decide which subset they can fill from their portal.
STANDARD_KEYS = (
    "tax_assessed_value",
    "tax_market_value",
    "tax_assessed_year",
    "lot_size_sqft",
    "lot_size_acres",
    "legal_description",
    "owner_name",
    "last_deed_date",
    "last_sale_price",
    "last_sale_date",
    "year_built_cad",
    "living_area_sqft_cad",
    "property_id",
)


class ArcGISParcelCAD(CountyCADSource):
    """Base class for county CADs whose data lives on an ArcGIS service.

    Subclasses set `service_url`, `attr_map`, and `sale_price_disclosed`.
    """

    service_url: str = ""
    attr_map: dict[str, list[str]] = {}
    sale_price_disclosed: bool = False
    timeout_s: float = 25.0

    # Query parameters; subclasses can override `query_params` to use
    # OBJECTID-where-clause-style queries instead of pure spatial.
    def query_params(self, address: Address) -> dict[str, str]:
        return {
            "f": "json",
            "geometry": f"{address.lon},{address.lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "false",
            "outSR": "4326",
        }

    def _pick(self, attrs: dict[str, Any], key: str) -> Any:
        """Look up a logical key (e.g. 'tax_assessed_value') in raw attrs.

        Walks the configured `attr_map[key]` aliases case-insensitively
        and returns the first non-empty value. Returns None on miss.
        """
        candidates = self.attr_map.get(key, [])
        if not candidates:
            return None
        norm = {k.upper(): v for k, v in attrs.items()}
        for alias in candidates:
            v = norm.get(alias.upper())
            if v not in (None, "", " ", 0):
                return v
        return None

    def fetch(self, address: Address) -> FetchResult:
        if not self.service_url:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"{self.name}: service_url not configured for {self.county_label}",
            )

        url = f"{self.service_url}/query"
        params = self.query_params(address)
        try:
            r = httpx.get(url, params=params, timeout=self.timeout_s)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as e:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"{self.name}: ArcGIS query failed for {self.county_label}: {e}",
            )

        if not isinstance(data, dict) or "error" in data:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"{self.name}: ArcGIS error envelope for {self.county_label}: {str(data)[:200]}",
            )

        features = data.get("features") or []
        if not features:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"{self.name}: no parcel polygon at point for {self.county_label} (not_found)",
            )

        attrs = features[0].get("attributes") or {}
        ref = f"{url} (county FIPS {self.full_county_fips})"

        facts: dict[str, Fact] = {}
        for key in STANDARD_KEYS:
            if key in {"last_sale_price"} and not self.sale_price_disclosed:
                continue
            val = self._pick(attrs, key)
            if val is None:
                continue
            note = None
            if key == "last_deed_date" and not self.sale_price_disclosed:
                note = "Texas non-disclosure — sale price not public"
            facts[key] = Fact(
                value=val, source=self.name, raw_ref=ref, note=note,
            )

        if not facts:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=(
                    f"{self.name}: parcel found but no mapped attributes "
                    f"yielded data — attr_map likely needs updating for {self.county_label}"
                ),
                raw=data,
            )

        return FetchResult(
            source_name=self.name, address=address, facts=facts, raw=data,
        )
