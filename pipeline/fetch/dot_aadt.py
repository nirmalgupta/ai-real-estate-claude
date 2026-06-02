"""DOT AADT (Annual Average Daily Traffic) — "is this on a busy road?"

Source: FHWA HPMS (Highway Performance Monitoring System), published as
per-state FeatureServers on the USDOT/BTS ArcGIS host:
    https://geo.dot.gov/server/rest/services/Hosted/HPMS_FULL_<ST>_<YEAR>/FeatureServer/0

No auth. Each segment carries an `aadt` field (average daily vehicle
count). We run two point-envelope queries around the property:

  - "frontage" (~150 m box): the busiest sampled road essentially at the
    doorstep — a proxy for road noise / traffic right on the lot.
  - "area"     (~1 mi box):   the busiest road in the immediate area —
    context for arterials/highways nearby.

HPMS only populates `aadt` on federal-aid / sampled roads, so quiet
residential streets correctly come back with no count (we filter
`aadt > 0`). The service is named by state + year; the latest year
varies per state, so we probe recent years newest-first and use the
first that resolves.
"""
from __future__ import annotations

import math

import httpx

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult, Source

HPMS_HOST = "https://geo.dot.gov/server/rest/services/Hosted"
# Newest-first; the first service that resolves for the state wins.
CANDIDATE_YEARS = [2024, 2023, 2022, 2021, 2020]

# FHWA functional-system codes → human label.
FUNCTIONAL_CLASS = {
    1: "Interstate",
    2: "Principal Arterial — Other Freeway/Expressway",
    3: "Principal Arterial — Other",
    4: "Minor Arterial",
    5: "Major Collector",
    6: "Minor Collector",
    7: "Local",
}

_MILES_PER_DEG_LAT = 69.0


def functional_class_label(code) -> str | None:
    """Map an HPMS f_system code to a readable label (None if unknown)."""
    try:
        return FUNCTIONAL_CLASS.get(int(code))
    except (TypeError, ValueError):
        return None


def envelope(lat: float, lon: float, miles: float) -> tuple[float, float, float, float]:
    """A lat/lon bounding box `miles` to a side's half-width around a point.

    Returns (xmin, ymin, xmax, ymax) in WGS84 degrees. Longitude degrees
    are scaled by cos(lat) so the box is roughly square on the ground.
    """
    dlat = miles / _MILES_PER_DEG_LAT
    # Guard the poles; cos(lat) → 0 would blow up the longitude span.
    cos_lat = max(math.cos(math.radians(lat)), 0.01)
    dlon = miles / (_MILES_PER_DEG_LAT * cos_lat)
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def pick_busiest(features: list[dict]) -> dict | None:
    """From ArcGIS features, return the attributes of the max-AADT segment."""
    best = None
    best_aadt = -1
    for f in features:
        attrs = f.get("attributes", {}) or {}
        aadt = attrs.get("aadt")
        if isinstance(aadt, (int, float)) and aadt > best_aadt:
            best_aadt = aadt
            best = attrs
    return best


def _road_label(attrs: dict) -> str | None:
    """Best human name for a segment: route name, else route id."""
    name = attrs.get("routename")
    if isinstance(name, str) and name.strip():
        return name.strip()
    rid = attrs.get("route_id")
    if isinstance(rid, str) and rid.strip():
        return rid.strip()
    return None


class DotAadtSource(Source):
    name = "dot_aadt"

    OUT_FIELDS = "route_id,routename,aadt,f_system,facility_type"

    def __init__(self, years: list[int] | None = None):
        self._years = years or CANDIDATE_YEARS

    def _service_url(self, state: str) -> str | None:
        """Probe recent years newest-first; return the first FeatureServer
        layer URL that resolves for this state, or None."""
        for year in self._years:
            base = f"{HPMS_HOST}/HPMS_FULL_{state}_{year}/FeatureServer"
            try:
                r = httpx.get(base, params={"f": "json"}, timeout=20.0)
                r.raise_for_status()
                meta = r.json()
            except (httpx.HTTPError, ValueError):
                continue
            if "error" in meta:
                continue
            layers = meta.get("layers") or []
            if layers:
                return f"{base}/{layers[0]['id']}/query"
        return None

    def _busiest_in_box(self, query_url: str, lat: float, lon: float,
                        miles: float) -> dict | None:
        xmin, ymin, xmax, ymax = envelope(lat, lon, miles)
        params = {
            "where": "aadt>0",
            "geometry": f"{xmin},{ymin},{xmax},{ymax}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": self.OUT_FIELDS,
            "returnGeometry": "false",
            "orderByFields": "aadt DESC",
            "resultRecordCount": "10",
            "f": "json",
        }
        r = httpx.get(query_url, params=params, timeout=30.0)
        r.raise_for_status()
        payload = r.json()
        if "error" in payload:
            raise httpx.HTTPError(f"ArcGIS query error: {payload['error']}")
        return pick_busiest(payload.get("features", []))

    def fetch(self, address: Address) -> FetchResult:
        state = (address.state_abbr or "").upper()
        if not state or len(state) != 2:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"DOT AADT: need a 2-letter state, got {state!r}.",
            )

        query_url = self._service_url(state)
        if query_url is None:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"DOT AADT: no HPMS service found for {state} "
                      f"(tried years {self._years}).",
            )

        try:
            area = self._busiest_in_box(query_url, address.lat, address.lon, 1.0)
            frontage = self._busiest_in_box(query_url, address.lat, address.lon, 0.1)
        except (httpx.HTTPError, ValueError) as e:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"DOT AADT fetch failed: {e}",
            )

        ref = query_url.rsplit("/query", 1)[0]
        facts: dict[str, Fact] = {}

        def add(key: str, value, note: str | None = None) -> None:
            if value is None:
                return
            facts[key] = Fact(value=value, source=self.name, raw_ref=ref, note=note)

        if area:
            add("area_max_aadt", int(area["aadt"]),
                note="busiest HPMS-sampled road within ~1 mi")
            add("area_max_aadt_road", _road_label(area))
            add("area_max_aadt_class", functional_class_label(area.get("f_system")))

        if frontage:
            add("frontage_aadt", int(frontage["aadt"]),
                note="busiest HPMS-sampled road within ~150 m of the parcel")
            add("frontage_aadt_road", _road_label(frontage))
            add("frontage_aadt_class", functional_class_label(frontage.get("f_system")))

        if not facts:
            # No sampled road nearby — a genuine signal (quiet area), not an error.
            add("area_max_aadt", 0,
                note="no HPMS-sampled road with a traffic count within ~1 mi")

        return FetchResult(
            source_name=self.name, address=address, facts=facts,
            raw={"state": state, "query_url": query_url},
        )
