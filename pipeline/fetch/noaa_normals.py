"""NOAA NCEI 30-year climate normals (1991-2020).

For a property lat/lon, find the nearest weather station and return its
annual climate normals: mean temperature, total precipitation, average
days >90°F, average days <32°F.

Source: https://www.ncei.noaa.gov/products/land-based-station/us-climate-normals
- Station inventory:
    https://www.ncei.noaa.gov/data/normals-annualseasonal/1991-2020/doc/inventory_30yr.txt
  Fixed-width text file with one row per station. ~17k US + territories
  stations, ~1.3 MB.
- Per-station CSV:
    https://www.ncei.noaa.gov/data/normals-annualseasonal/1991-2020/access/<STATION_ID>.csv
  CSV with all 30-year normals fields for one station.

Both files are cached under ~/.cache/ai-real-estate-pipeline/normals/
so subsequent runs (and tests) are local.

Inventory column positions (fixed-width):
    1-11   station id
    13-20  latitude (decimal degrees, can be negative)
    22-30  longitude (decimal degrees, can be negative)
    32-37  elevation (meters)
    39-40  state/territory code
    42+    station name + extras

Not every station carries every normals field — many co-op stations
only have precip. We pick the nearest station that has a non-blank
ANN-TAVG-NORMAL, since temperature is the most user-visible field. The
issue (#44) only asks for annual aggregates, so this gives the cleanest
output without surfacing partial data.
"""
from __future__ import annotations

import csv
import io
import math
from pathlib import Path

import httpx

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult, Source

INVENTORY_URL = (
    "https://www.ncei.noaa.gov/data/normals-annualseasonal/1991-2020/"
    "doc/inventory_30yr.txt"
)
STATION_BASE = (
    "https://www.ncei.noaa.gov/data/normals-annualseasonal/1991-2020/access"
)

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "ai-real-estate-pipeline" / "normals"

# Fields we surface. NCEI names are stable across the 1991-2020 release;
# they may shift in future releases, so we centralize the mapping.
TARGET_FIELDS = {
    "annual_mean_temp_f": "ANN-TAVG-NORMAL",
    "annual_precip_inches": "ANN-PRCP-NORMAL",
    "days_above_90f": "ANN-TMAX-AVGNDS-GRTH090",
    "days_below_32f": "ANN-TMIN-AVGNDS-LSTH032",
}


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3958.7613
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _parse_inventory(text: str) -> list[dict]:
    """Parse the fixed-width inventory file. Returns one dict per station."""
    rows: list[dict] = []
    for line in text.splitlines():
        if len(line) < 40:
            continue
        try:
            sid = line[0:11].strip()
            lat = float(line[12:20].strip())
            lon = float(line[21:30].strip())
            state = line[38:40].strip()
            name = line[41:].strip().split()[0:6]
            if not sid:
                continue
            rows.append({
                "id": sid,
                "lat": lat,
                "lon": lon,
                "state": state,
                "name": " ".join(name) if name else sid,
            })
        except (ValueError, IndexError):
            continue
    return rows


def _nearest_stations(stations: list[dict], lat: float, lon: float,
                      k: int = 10) -> list[tuple[float, dict]]:
    """Return the k stations nearest to (lat, lon), sorted ascending by distance."""
    scored = [(_haversine_miles(lat, lon, s["lat"], s["lon"]), s) for s in stations]
    scored.sort(key=lambda t: t[0])
    return scored[:k]


def _parse_station_csv(text: str) -> dict[str, float | None]:
    """Pull our four target fields out of a per-station normals CSV.

    NCEI CSVs are wide-format: header row + one data row per period.
    Annual normals appear on the row whose date column is 'ANNUAL' or
    similar — but the ANN- prefixed columns make the row choice moot.
    We just grab the first non-blank value across all data rows for
    each target column.
    """
    rdr = list(csv.reader(io.StringIO(text)))
    if not rdr:
        return {k: None for k in TARGET_FIELDS}
    headers = rdr[0]
    out: dict[str, float | None] = {k: None for k in TARGET_FIELDS}
    for our_key, ncei_key in TARGET_FIELDS.items():
        if ncei_key not in headers:
            continue
        col = headers.index(ncei_key)
        for row in rdr[1:]:
            if col >= len(row):
                continue
            v = row[col].strip()
            if not v or v in {"-9999", "-7777", "-6666", "-5555"}:
                continue
            try:
                out[our_key] = float(v)
                break
            except ValueError:
                continue
    return out


def _fetch_cached(url: str, cache_path: Path, timeout: float = 30.0) -> str | None:
    """GET `url` with on-disk caching. Returns body or None on failure."""
    if cache_path.exists() and cache_path.stat().st_size > 0:
        try:
            return cache_path.read_text()
        except OSError:
            pass
    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True)
        r.raise_for_status()
    except httpx.HTTPError:
        return None
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        cache_path.write_text(r.text)
    except OSError:
        pass
    return r.text


class NoaaNormalsSource(Source):
    name = "noaa_normals"

    def __init__(self, cache_dir: Path = DEFAULT_CACHE_DIR):
        self.cache_dir = cache_dir

    def fetch(self, address: Address) -> FetchResult:
        inv_text = _fetch_cached(
            INVENTORY_URL, self.cache_dir / "inventory_30yr.txt",
        )
        if not inv_text:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error="NOAA normals inventory fetch failed.",
            )

        stations = _parse_inventory(inv_text)
        if not stations:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error="NOAA normals inventory parsed empty.",
            )

        # Try the nearest 10 stations; many co-op stations have no
        # temperature data. Stop at the first one with a usable record.
        chosen = None
        parsed: dict[str, float | None] = {}
        distance_miles = None
        for dist, st in _nearest_stations(stations, address.lat, address.lon, k=10):
            csv_url = f"{STATION_BASE}/{st['id']}.csv"
            body = _fetch_cached(csv_url, self.cache_dir / f"{st['id']}.csv")
            if not body:
                continue
            parsed = _parse_station_csv(body)
            if parsed.get("annual_mean_temp_f") is not None:
                chosen = st
                distance_miles = dist
                break

        if chosen is None:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error="No NOAA normals station within search radius had "
                      "annual temperature data.",
            )

        station_url = f"{STATION_BASE}/{chosen['id']}.csv"
        facts: dict[str, Fact] = {}

        def add(key: str, value, note: str | None = None) -> None:
            if value is None:
                return
            facts[key] = Fact(
                value=value, source=self.name, raw_ref=station_url, note=note,
            )

        for our_key, _ncei_key in TARGET_FIELDS.items():
            add(our_key, parsed.get(our_key))

        add("normals_station_id", chosen["id"])
        add("normals_station_name", chosen["name"])
        add("normals_station_distance_miles", round(distance_miles, 1))

        return FetchResult(
            source_name=self.name, address=address, facts=facts,
            raw={"station": chosen, "distance_miles": distance_miles},
        )
