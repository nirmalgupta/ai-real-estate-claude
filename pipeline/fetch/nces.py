"""NCES public-school fetcher.

Pulls the nearest public schools to a property's lat/lon from the NCES
EDGE Geocode Public Schools service (ArcGIS REST). NCES is the federal
authority on public-school data: enrollment, grade range, locale, FRL %,
demographics. It does NOT publish ratings — those are GreatSchools/Niche
territory.

Service:
    https://nces.ed.gov/opengis/rest/services/Customer_Specific/...

The pipeline only needs nearest-N schools, not district boundaries, so we
issue a spatial buffer query and rank by haversine distance client-side.
The ArcGIS layer URL has rolled forward by school-year, so we try a small
ordered list of recent years until one returns 200.
"""
from __future__ import annotations

import math
from typing import Any

import httpx

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult, Source

NCES_BASE = "https://nces.ed.gov/opengis/rest/services"

# Ordered newest → older. Layer 1 = points; layer 0 may be polygons.
# Each year's layer rolls in the fall after the school year ends.
LAYER_CANDIDATES = [
    f"{NCES_BASE}/Customer_Specific/EDGE_GEOCODE_PUBLICSCH_2324/MapServer/1",
    f"{NCES_BASE}/Customer_Specific/EDGE_GEOCODE_PUBLICSCH_2223/MapServer/1",
    f"{NCES_BASE}/Customer_Specific/EDGE_GEOCODE_PUBLICSCH_2122/MapServer/1",
    f"{NCES_BASE}/Customer_Specific/EDGE_GEOCODE_PUBLICSCH/MapServer/1",
]

SEARCH_RADIUS_MILES = 8.0  # generous enough for rural; nearest-3 will be much closer in cities
MAX_PER_LEVEL = 3


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles."""
    r = 3958.7613
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _classify_level(grade_low: str | None, grade_high: str | None) -> str:
    """Bucket a school as elementary / middle / high based on grade span.

    NCES grade codes: PK, KG, 01..12. Elementary: PK-05; Middle: 06-08;
    High: 09-12. Mixed-grade schools (e.g. K-8) get classified by their
    high grade — that's how NCES's own SCH_TYPE rolls.
    """
    g = (grade_high or "").strip().upper()
    if g in {"01", "02", "03", "04", "05", "KG", "PK"}:
        return "elementary"
    if g in {"06", "07", "08"}:
        return "middle"
    if g in {"09", "10", "11", "12"}:
        return "high"
    return "other"


def _query_layer(layer_url: str, address: Address) -> tuple[list[dict[str, Any]], str] | None:
    """Spatial buffer query against one MapServer layer.

    Returns (features, raw_ref) on HTTP 200 with parseable JSON. Returns
    None if the layer is unreachable or returns an ArcGIS error envelope —
    the caller will fall through to the next year's layer.
    """
    params = {
        "f": "json",
        "geometry": f"{address.lon},{address.lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "distance": str(SEARCH_RADIUS_MILES),
        "units": "esriSRUnit_StatuteMile",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
    }
    query_url = f"{layer_url}/query"
    try:
        r = httpx.get(query_url, params=params, timeout=30.0)
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not isinstance(data, dict) or "error" in data:
        return None
    features = data.get("features") or []
    if not isinstance(features, list):
        return None
    return features, query_url


def _get(attrs: dict[str, Any], *keys: str) -> Any:
    """Case-insensitive lookup over a few candidate keys.

    NCES has shipped the same field with different capitalizations across
    layer-year vintages (NAME vs SCH_NAME vs Name). Try each.
    """
    norm = {k.upper(): v for k, v in attrs.items()}
    for k in keys:
        v = norm.get(k.upper())
        if v not in (None, "", " "):
            return v
    return None


class NCESSource(Source):
    name = "nces_publicsch"

    def fetch(self, address: Address) -> FetchResult:
        result_features: list[dict[str, Any]] | None = None
        ref: str | None = None
        for layer_url in LAYER_CANDIDATES:
            res = _query_layer(layer_url, address)
            if res is not None and res[0]:
                result_features, ref = res
                break

        if result_features is None:
            return FetchResult(
                source_name=self.name,
                address=address,
                facts={},
                error=(
                    "NCES EDGE returned no school features for "
                    f"{address.lat:.4f},{address.lon:.4f} from any tried layer "
                    f"({len(LAYER_CANDIDATES)} attempts)."
                ),
            )

        # Rank by haversine distance — server-side buffer is approximate.
        ranked: list[tuple[float, dict[str, Any]]] = []
        for feat in result_features:
            geom = feat.get("geometry") or {}
            attrs = feat.get("attributes") or {}
            lat = geom.get("y")
            lon = geom.get("x")
            if lat is None or lon is None:
                continue
            d = _haversine_miles(address.lat, address.lon, float(lat), float(lon))
            ranked.append((d, attrs))
        ranked.sort(key=lambda t: t[0])

        # Group by level, keep nearest MAX_PER_LEVEL per level.
        by_level: dict[str, list[dict[str, Any]]] = {
            "elementary": [], "middle": [], "high": [], "other": [],
        }
        for dist, attrs in ranked:
            level = _classify_level(
                _get(attrs, "GSLO", "GRADE_LOW"),
                _get(attrs, "GSHI", "GRADE_HIGH"),
            )
            if len(by_level[level]) < MAX_PER_LEVEL:
                by_level[level].append({
                    "name": _get(attrs, "NAME", "SCH_NAME"),
                    "city": _get(attrs, "CITY", "LCITY"),
                    "state": _get(attrs, "STATE", "LSTATE"),
                    "lea": _get(attrs, "LEA_NAME", "LEANM"),
                    "nces_school_id": _get(attrs, "NCESSCH"),
                    "enrollment": _get(attrs, "MEMBER", "ENROLLMENT"),
                    "locale_code": _get(attrs, "ULOCALE", "LOCALE"),
                    "grade_low": _get(attrs, "GSLO", "GRADE_LOW"),
                    "grade_high": _get(attrs, "GSHI", "GRADE_HIGH"),
                    "distance_miles": round(dist, 2),
                })

        facts: dict[str, Fact] = {}
        for level in ("elementary", "middle", "high"):
            schools = by_level[level]
            if schools:
                facts[f"nearest_{level}_schools"] = Fact(
                    value=schools, source=self.name, raw_ref=ref,
                )

        if not facts:
            return FetchResult(
                source_name=self.name,
                address=address,
                facts={},
                error="NCES EDGE returned features but none classified by grade level.",
            )

        return FetchResult(
            source_name=self.name,
            address=address,
            facts=facts,
            raw={"feature_count": len(result_features), "layer": ref},
        )
