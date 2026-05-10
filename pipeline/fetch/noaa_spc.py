"""NOAA SPC storm-history fetcher.

For each property lat/lon, returns 10-year counts of severe-storm events
within a 10-mile radius:
    - EF1+ tornadoes
    - hail events with reported size ≥ 1.5"
    - convective wind events with measured/estimated speed ≥ 58 mph

Data source: NOAA Storm Prediction Center's annual severe-weather CSVs
at https://www.spc.noaa.gov/wcm/data/<year>_<type>.csv

Each CSV is small (~150 KB), but we still cache the per-year file under
~/.cache/ai-real-estate-pipeline/spc/ so subsequent runs are local.

The CSVs are only the schema NOAA documents at
    https://www.spc.noaa.gov/wcm/  (see "SPC Severe Weather Database")

The choice of CSVs over an ArcGIS service is deliberate: the SPC SVRGIS
endpoint is not a stable public point-query API, but the CSVs have been
the canonical archive since 1950.
"""
from __future__ import annotations

import csv
import io
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult, Source

SPC_BASE = "https://www.spc.noaa.gov/wcm/data"

RADIUS_MILES = 10.0
LOOKBACK_YEARS = 10

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "ai-real-estate-pipeline" / "spc"


# CSV column indexes for tornado, hail, wind. SPC's schema is fixed and
# documented at https://www.spc.noaa.gov/wcm/. Tornadoes have separate
# slat/slon (start) and elat/elon (end); hail and wind have a single
# slat/slon point.
TORN_COLS = {"yr": 1, "mag": 10, "slat": 15, "slon": 16}
HAIL_COLS = {"yr": 1, "mag": 10, "slat": 15, "slon": 16}
WIND_COLS = {"yr": 1, "mag": 10, "slat": 15, "slon": 16}


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3958.7613
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _cache_path(cache_dir: Path, year: int, kind: str) -> Path:
    return cache_dir / f"{year}_{kind}.csv"


def _fetch_year_csv(year: int, kind: str, cache_dir: Path) -> str | None:
    """Return CSV body for a (year, kind), via cache or HTTP. None on failure."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = _cache_path(cache_dir, year, kind)
    if cache_file.exists() and cache_file.stat().st_size > 0:
        try:
            return cache_file.read_text()
        except OSError:
            pass

    url = f"{SPC_BASE}/{year}_{kind}.csv"
    try:
        r = httpx.get(url, timeout=30.0)
        r.raise_for_status()
        body = r.text
    except (httpx.HTTPError, ValueError):
        return None
    try:
        cache_file.write_text(body)
    except OSError:
        pass
    return body


def _count_in_csv(
    csv_body: str,
    cols: dict[str, int],
    address: Address,
    *,
    mag_min: float,
) -> int:
    """Count rows whose start lat/lon is within RADIUS_MILES and mag ≥ threshold."""
    count = 0
    reader = csv.reader(io.StringIO(csv_body))
    next(reader, None)  # header
    for row in reader:
        if len(row) <= cols["slon"]:
            continue
        try:
            mag = float(row[cols["mag"]] or "0")
            slat = float(row[cols["slat"]] or "0")
            slon = float(row[cols["slon"]] or "0")
        except ValueError:
            continue
        if mag < mag_min or slat == 0 or slon == 0:
            continue
        if _haversine_miles(address.lat, address.lon, slat, slon) <= RADIUS_MILES:
            count += 1
    return count


class NoaaSpcSource(Source):
    name = "noaa_spc"

    def __init__(self, cache_dir: Path | None = None) -> None:
        env = os.environ.get("AI_RE_SPC_CACHE_DIR")
        self.cache_dir = (
            cache_dir or (Path(env) if env else DEFAULT_CACHE_DIR)
        )

    def fetch(self, address: Address) -> FetchResult:
        end_year = datetime.now(timezone.utc).year - 1   # SPC publishes prior year
        start_year = end_year - LOOKBACK_YEARS + 1

        thresholds = {
            "torn": (TORN_COLS, 1.0,  "EF1+ tornadoes"),
            "hail": (HAIL_COLS, 1.5,  "Hail ≥1.5\""),
            "wind": (WIND_COLS, 58.0, "Convective wind ≥58mph"),
        }

        counts: dict[str, int] = {k: 0 for k in thresholds}
        years_covered: dict[str, int] = {k: 0 for k in thresholds}

        for kind, (cols, mag_min, _label) in thresholds.items():
            for year in range(start_year, end_year + 1):
                body = _fetch_year_csv(year, kind, self.cache_dir)
                if body is None:
                    continue
                counts[kind] += _count_in_csv(body, cols, address, mag_min=mag_min)
                years_covered[kind] += 1

        if all(years_covered[k] == 0 for k in thresholds):
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=(
                    "NOAA SPC severe-weather CSVs unreachable for all event types "
                    f"(years {start_year}–{end_year})."
                ),
            )

        ref = f"{SPC_BASE}/<year>_<torn|hail|wind>.csv  (years {start_year}-{end_year})"
        facts: dict[str, Fact] = {}

        if years_covered["torn"]:
            facts["storm_tornado_ef1plus_10yr_count"] = Fact(
                value=counts["torn"], source=self.name, raw_ref=ref,
                note=(f"Tornadoes EF1+ within {RADIUS_MILES}mi, "
                      f"{years_covered['torn']} of {LOOKBACK_YEARS} yr files matched"),
            )
        if years_covered["hail"]:
            facts["storm_hail_15in_plus_10yr_count"] = Fact(
                value=counts["hail"], source=self.name, raw_ref=ref,
                note=(f"Hail ≥1.5\" within {RADIUS_MILES}mi, "
                      f"{years_covered['hail']} of {LOOKBACK_YEARS} yr files matched"),
            )
        if years_covered["wind"]:
            facts["storm_wind_58mph_plus_10yr_count"] = Fact(
                value=counts["wind"], source=self.name, raw_ref=ref,
                note=(f"Convective wind ≥58mph within {RADIUS_MILES}mi, "
                      f"{years_covered['wind']} of {LOOKBACK_YEARS} yr files matched"),
            )

        return FetchResult(
            source_name=self.name, address=address, facts=facts,
            raw={"years_covered": years_covered, "window": (start_year, end_year)},
        )
