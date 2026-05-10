"""Redfin gis-csv multi-listing search.

Endpoint:
    GET https://www.redfin.com/stingray/api/gis-csv
        ?al=1
        &num_homes=<N>
        &page_number=1
        &poly=<lon1 lat1,lon2 lat2,...,lon1 lat1>   # closed polygon
        &sf=1,2,3,5,6,7                             # sale-type filter
        &status=<see STATUS_*>                      # listing status
        &uipt=1,2,3,4,5,6,7,8                       # property-type filter
        &v=8

Returns CSV with one row per listing. Schema is documented in the file's
header row but the columns are fixed as of 2026-05.

This module is read-only and cheap: one HTTP call per search,
~10–500 KB response.
"""
from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass

import httpx

GIS_CSV = "https://www.redfin.com/stingray/api/gis-csv"

# Redfin status codes
STATUS_ACTIVE = 9          # for-sale active
STATUS_SOLD = 1            # sold (used with --sold-since)
STATUS_PENDING = 130       # pending
STATUS_CONTINGENT = 131    # contingent

# uipt = User Input Property Type. 1=house, 2=condo, 3=townhouse,
# 4=multi-family, 5=land, 6=other, 7=mobile, 8=co-op.
DEFAULT_PROPERTY_TYPES = "1,2,3,4"   # exclude land/mobile/co-op by default

# Realistic browser UA — Redfin returns 200 to plain HTTP with this UA
# but sometimes 403s the python-httpx default.
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class Listing:
    """One row from gis-csv, normalized."""
    address: str
    city: str
    state: str
    zip: str
    price: int | None
    beds: int | None
    baths: float | None
    sqft: int | None
    lot_sqft: int | None
    year_built: int | None
    days_on_market: int | None
    price_per_sqft: int | None
    hoa_monthly: int | None
    status: str
    property_type: str
    mls_number: str
    url: str
    lat: float | None
    lon: float | None

    @property
    def display_addr(self) -> str:
        return f"{self.address}, {self.city}, {self.state} {self.zip}".strip(", ")


def _bbox_polygon(
    center_lat: float, center_lon: float, radius_miles: float,
) -> str:
    """Build a closed-square polygon string suitable for the `poly` param.

    Square buffer is good enough for the search UX and avoids hauling in a
    geometry library. Latitude:  1° ≈ 69.0 mi (constant).
    Longitude: 1° ≈ 69.172 * cos(lat) mi (shrinks toward the poles).
    """
    lat_delta = radius_miles / 69.0
    lon_delta = radius_miles / (69.172 * math.cos(math.radians(center_lat)))
    n = center_lat + lat_delta
    s = center_lat - lat_delta
    e = center_lon + lon_delta
    w = center_lon - lon_delta
    # Closed polygon: SW, SE, NE, NW, SW. lon then lat, space-separated.
    pts = [(w, s), (e, s), (e, n), (w, n), (w, s)]
    return ",".join(f"{lon:.6f} {lat:.6f}" for lon, lat in pts)


def _row_int(row: dict[str, str], key: str) -> int | None:
    v = (row.get(key) or "").replace(",", "").strip()
    if not v:
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _row_float(row: dict[str, str], key: str) -> float | None:
    v = (row.get(key) or "").replace(",", "").strip()
    if not v:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_csv(body: str) -> list[Listing]:
    """Parse the gis-csv body into a list of Listing dataclasses.

    The first row sometimes contains an MLS-restriction notice instead of
    a listing — we skip rows whose ADDRESS is empty.
    """
    listings: list[Listing] = []
    reader = csv.DictReader(io.StringIO(body))
    for row in reader:
        addr = (row.get("ADDRESS") or "").strip()
        if not addr:
            continue
        listings.append(Listing(
            address=addr,
            city=(row.get("CITY") or "").strip(),
            state=(row.get("STATE OR PROVINCE") or "").strip(),
            zip=(row.get("ZIP OR POSTAL CODE") or "").strip(),
            price=_row_int(row, "PRICE"),
            beds=_row_int(row, "BEDS"),
            baths=_row_float(row, "BATHS"),
            sqft=_row_int(row, "SQUARE FEET"),
            lot_sqft=_row_int(row, "LOT SIZE"),
            year_built=_row_int(row, "YEAR BUILT"),
            days_on_market=_row_int(row, "DAYS ON MARKET"),
            price_per_sqft=_row_int(row, "$/SQUARE FEET"),
            hoa_monthly=_row_int(row, "HOA/MONTH"),
            status=(row.get("STATUS") or "").strip(),
            property_type=(row.get("PROPERTY TYPE") or "").strip(),
            mls_number=(row.get("MLS#") or "").strip(),
            url=(
                (row.get("URL (SEE https://www.redfin.com/buy-a-home/comparative-market-analysis FOR INFO ON PRICING)")
                 or "").strip()
            ),
            lat=_row_float(row, "LATITUDE"),
            lon=_row_float(row, "LONGITUDE"),
        ))
    return listings


def search_redfin(
    *,
    center_lat: float,
    center_lon: float,
    radius_miles: float = 3.0,
    max_results: int = 50,
    min_price: int | None = None,
    max_price: int | None = None,
    min_beds: int | None = None,
    min_baths: float | None = None,
    property_types: str = DEFAULT_PROPERTY_TYPES,
    status: int = STATUS_ACTIVE,
) -> tuple[list[Listing], str]:
    """Search Redfin for active listings in a bbox around (lat, lon).

    Returns (listings, query_url). Filtering by price/beds/baths is done
    client-side after the fetch — gis-csv accepts these as URL params
    too, but server-side filtering has been less reliable across regions.
    """
    poly = _bbox_polygon(center_lat, center_lon, radius_miles)
    params = {
        "al": "1",
        "num_homes": str(max_results),
        "page_number": "1",
        "poly": poly,
        "sf": "1,2,3,5,6,7",
        "status": str(status),
        "uipt": property_types,
        "v": "8",
    }
    headers = {
        "User-Agent": BROWSER_UA,
        "Accept": "text/csv,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    r = httpx.get(GIS_CSV, params=params, headers=headers, timeout=30.0,
                  follow_redirects=True)
    r.raise_for_status()
    listings = _parse_csv(r.text)

    # Client-side filter pass.
    def keep(L: Listing) -> bool:
        if min_price is not None and (L.price or 0) < min_price:
            return False
        if max_price is not None and (L.price or 10**12) > max_price:
            return False
        if min_beds is not None and (L.beds or 0) < min_beds:
            return False
        if min_baths is not None and (L.baths or 0.0) < min_baths:
            return False
        return True

    return [L for L in listings if keep(L)], str(r.request.url)
