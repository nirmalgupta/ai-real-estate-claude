"""NOAA SPC / NCEI storm-history fetcher.

For each property lat/lon, returns 10-year counts of severe-storm events
within a 10-mile radius:
    - EF1+ tornadoes
    - hail events with reported size ≥ 1.5"
    - convective wind events with measured/estimated speed ≥ 58 mph

Backed by NOAA NCEI's public ArcGIS map service for severe-weather
events. Each event class is its own layer; we issue one spatial+temporal
query per layer and count features.

Failure modes:
    - Service unreachable → FetchResult.error set, pipeline continues.
    - Zero features → all three counts return 0 (genuinely no events).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult, Source

NCEI_BASE = "https://maps.ncei.noaa.gov/server/rest/services"

# These layer URLs follow NCEI's published severe-thunderstorm events
# service. If the service moves, the fetcher returns a clean error.
TORNADO_LAYER = (
    f"{NCEI_BASE}/ncei_severe_thunderstorm_events/MapServer/0"  # tornado tracks
)
HAIL_LAYER = (
    f"{NCEI_BASE}/ncei_severe_thunderstorm_events/MapServer/1"
)
WIND_LAYER = (
    f"{NCEI_BASE}/ncei_severe_thunderstorm_events/MapServer/2"
)

RADIUS_MILES = 10.0
LOOKBACK_YEARS = 10


def _epoch_ms(dt: datetime) -> int:
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)


def _date_range_clause(years: int, date_field: str) -> str:
    """Build an ArcGIS WHERE clause for the last N years on `date_field`.

    NCEI services historically expose a TIMESTAMP-typed column; using
    a yyyy-MM-dd literal works on both Postgres- and Esri-FileGDB-backed
    services.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365 * years)
    s = start.strftime("%Y-%m-%d")
    e = end.strftime("%Y-%m-%d")
    return f"{date_field} >= DATE '{s}' AND {date_field} <= DATE '{e}'"


def _count_features(
    layer_url: str,
    address: Address,
    extra_where: str | None = None,
) -> tuple[int | None, str]:
    """Spatial+attribute count query against one ArcGIS layer.

    Returns (count, query_url). If the service is unreachable or returns
    an error envelope, count is None.
    """
    where = "1=1"
    if extra_where:
        where = extra_where
    params: dict[str, Any] = {
        "f": "json",
        "where": where,
        "geometry": f"{address.lon},{address.lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "distance": str(RADIUS_MILES),
        "units": "esriSRUnit_StatuteMile",
        "returnCountOnly": "true",
    }
    query_url = f"{layer_url}/query"
    try:
        r = httpx.get(query_url, params=params, timeout=30.0)
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError):
        return None, query_url
    if not isinstance(data, dict) or "error" in data:
        return None, query_url
    count = data.get("count")
    if isinstance(count, int):
        return count, query_url
    return None, query_url


class NoaaSpcSource(Source):
    name = "noaa_spc"

    def fetch(self, address: Address) -> FetchResult:
        # NCEI fields: tornado magnitude is `MAGNITUDE` (EF scale int);
        # hail magnitude is inches; wind magnitude is mph.
        date_clause = _date_range_clause(LOOKBACK_YEARS, "BEGIN_DATE")

        tornado_where = f"{date_clause} AND MAGNITUDE >= 1"
        hail_where = f"{date_clause} AND MAGNITUDE >= 1.5"
        wind_where = f"{date_clause} AND MAGNITUDE >= 58"

        tornado_count, tornado_ref = _count_features(TORNADO_LAYER, address, tornado_where)
        hail_count, hail_ref = _count_features(HAIL_LAYER, address, hail_where)
        wind_count, wind_ref = _count_features(WIND_LAYER, address, wind_where)

        if tornado_count is None and hail_count is None and wind_count is None:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=(
                    "NOAA NCEI severe-storm service unreachable for all three "
                    f"event classes (last {LOOKBACK_YEARS}yr, {RADIUS_MILES}mi)."
                ),
            )

        facts: dict[str, Fact] = {}

        def add(key: str, value: int | None, ref: str, note: str) -> None:
            if value is None:
                return
            facts[key] = Fact(value=value, source=self.name, raw_ref=ref, note=note)

        add("storm_tornado_ef1plus_10yr_count", tornado_count, tornado_ref,
            f"Tornadoes EF1+ within {RADIUS_MILES}mi, last {LOOKBACK_YEARS}yr")
        add("storm_hail_15in_plus_10yr_count", hail_count, hail_ref,
            f"Hail ≥1.5\" within {RADIUS_MILES}mi, last {LOOKBACK_YEARS}yr")
        add("storm_wind_58mph_plus_10yr_count", wind_count, wind_ref,
            f"Convective wind ≥58mph within {RADIUS_MILES}mi, last {LOOKBACK_YEARS}yr")

        return FetchResult(
            source_name=self.name, address=address, facts=facts,
            raw={"tornado_ref": tornado_ref, "hail_ref": hail_ref, "wind_ref": wind_ref},
        )
