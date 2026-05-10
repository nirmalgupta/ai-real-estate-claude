"""Reusable ArcGIS REST parcel base class.

Matching strategy:
    1. Exact point-in-polygon query at the geocoded lat/lon (no buffer).
    2. If that returns zero features (the geocoded point landed in a
       road or right-of-way), retry with a small buffer and pick the
       parcel whose centroid is nearest to the geocoded point.

Step 2 is necessary because Census/Nominatim sometimes drop the address
point ~10m off the parcel polygon. Step 1 is the precise ground truth
when it succeeds.


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

import math
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
    "tax_appraised_value",
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
    "situs_address",
)


class ArcGISParcelCAD(CountyCADSource):
    """Base class for county CADs whose data lives on an ArcGIS service.

    Subclasses set `service_url`, `attr_map`, and `sale_price_disclosed`.
    """

    service_url: str = ""
    attr_map: dict[str, list[str]] = {}
    sale_price_disclosed: bool = False
    timeout_s: float = 25.0
    # Fallback buffer used when the exact point lands in a road or
    # right-of-way and no parcel polygon contains it. Kept small so
    # we don't bleed into multiple lots in dense subdivisions.
    spatial_buffer_miles: float = 0.02

    # Query parameters; subclasses can override `query_params` to use
    # OBJECTID-where-clause-style queries instead of pure spatial.
    def query_params(
        self, address: Address, *, buffer_miles: float = 0.0,
    ) -> dict[str, str]:
        params: dict[str, str] = {
            "f": "json",
            "where": "1=1",
            "geometry": f"{address.lon},{address.lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
        }
        if buffer_miles > 0:
            params["distance"] = str(buffer_miles)
            params["units"] = "esriSRUnit_StatuteMile"
        return params

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

    def _query(self, address: Address, buffer_miles: float) -> tuple[list[dict[str, Any]] | None, str]:
        """Run one ArcGIS query and return (features_or_none, query_url)."""
        url = f"{self.service_url}/query"
        params = self.query_params(address, buffer_miles=buffer_miles)
        try:
            r = httpx.get(url, params=params, timeout=self.timeout_s)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError):
            return None, url
        if not isinstance(data, dict) or "error" in data:
            return None, url
        features = data.get("features")
        if not isinstance(features, list):
            return None, url
        return features, url

    @staticmethod
    def _parcel_centroid(geom: dict[str, Any]) -> tuple[float, float] | None:
        """Approximate centroid of an ArcGIS polygon geometry."""
        rings = geom.get("rings") if isinstance(geom, dict) else None
        if not rings or not isinstance(rings, list) or not rings[0]:
            return None
        ring = rings[0]
        xs = [p[0] for p in ring if isinstance(p, list) and len(p) >= 2]
        ys = [p[1] for p in ring if isinstance(p, list) and len(p) >= 2]
        if not xs or not ys:
            return None
        return sum(xs) / len(xs), sum(ys) / len(ys)

    @staticmethod
    def _distance_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        r = 3958.7613
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * r * math.asin(math.sqrt(a))

    def _pick_best_feature(
        self, features: list[dict[str, Any]], address: Address,
    ) -> dict[str, Any]:
        """When multiple features match, return the one closest to the geocoded point."""
        if len(features) <= 1:
            return features[0]
        ranked: list[tuple[float, dict[str, Any]]] = []
        for f in features:
            cen = self._parcel_centroid(f.get("geometry") or {})
            if cen is None:
                continue
            d = self._distance_miles(address.lat, address.lon, cen[1], cen[0])
            ranked.append((d, f))
        if not ranked:
            return features[0]
        ranked.sort(key=lambda t: t[0])
        return ranked[0][1]

    def fetch(self, address: Address) -> FetchResult:
        if not self.service_url:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"{self.name}: service_url not configured for {self.county_label}",
            )

        # Pass 1: exact point-in-polygon. Most properties land here.
        features, url = self._query(address, buffer_miles=0.0)
        if features is None:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"{self.name}: ArcGIS query failed for {self.county_label}",
            )

        # Pass 2: small buffer fallback for geocoded points that miss
        # the parcel polygon by a few meters (road / right-of-way).
        if not features and self.spatial_buffer_miles > 0:
            features, url = self._query(
                address, buffer_miles=self.spatial_buffer_miles
            )
            if features is None:
                return FetchResult(
                    source_name=self.name, address=address, facts={},
                    error=f"{self.name}: ArcGIS buffered query failed for {self.county_label}",
                )

        if not features:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"{self.name}: no parcel polygon at point for {self.county_label} (not_found)",
            )

        feat = self._pick_best_feature(features, address)
        attrs = feat.get("attributes") or {}
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
                raw={"feature": feat},
            )

        return FetchResult(
            source_name=self.name, address=address, facts=facts,
            raw={"feature": feat},
        )
