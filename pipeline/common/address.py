"""Canonical address handling.

Primary geocoder: US Census Geocoder (free, no key, returns FIPS codes).
Fallback: Nominatim (lat/lon) + FCC Block API (lat/lon → FIPS). Used when
Census is having one of its frequent outages.

The FIPS codes the rest of the pipeline depends on come from one of these
two paths. We always end up with: lat, lon, state_fips, county_fips,
tract_fips.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

import httpx

CENSUS_GEOCODER = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
FCC_BLOCK = "https://geo.fcc.gov/api/census/block/find"

NOMINATIM_UA = "ai-real-estate-pipeline/0.1 (https://github.com/nirmal/ai-real-estate-claude)"

RETRY_STATUSES = {500, 502, 503, 504}


@dataclass
class Address:
    raw: str
    matched: str
    lat: float
    lon: float
    state_fips: str
    county_fips: str
    tract_fips: str
    block_fips: str
    state_abbr: str
    county_name: str
    zip: str

    @property
    def slug(self) -> str:
        s = re.sub(r"[^\w\s-]", "", self.matched).strip().lower()
        return re.sub(r"[\s_-]+", "-", s)[:80]

    @property
    def full_county_fips(self) -> str:
        return f"{self.state_fips}{self.county_fips}"

    @property
    def full_tract_fips(self) -> str:
        return f"{self.state_fips}{self.county_fips}{self.tract_fips}"


def _retry_get(url: str, params: dict, *, headers: dict | None = None,
               timeout: float = 30.0, max_retries: int = 4) -> httpx.Response:
    """GET with exponential-backoff retry on connection / 5xx errors."""
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            r = httpx.get(url, params=params, headers=headers or {}, timeout=timeout)
        except httpx.RequestError as e:
            last_err = e
        else:
            if r.status_code in RETRY_STATUSES:
                last_err = httpx.HTTPStatusError(
                    f"transient {r.status_code}", request=r.request, response=r
                )
            else:
                r.raise_for_status()
                return r
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"{url} unreachable after {max_retries} attempts: {last_err}")


def _try_census(address: str) -> Address | None:
    """One-call path. Returns None if the geocoder is unreachable or has no match."""
    params = {
        "address": address,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "format": "json",
    }
    try:
        r = _retry_get(CENSUS_GEOCODER, params=params)
    except RuntimeError:
        return None

    matches = r.json().get("result", {}).get("addressMatches", [])
    if not matches:
        return None

    m = matches[0]
    coords = m["coordinates"]
    geo = m["geographies"]
    tract = geo["Census Tracts"][0]
    county = geo["Counties"][0]
    state = geo["States"][0]
    block = geo.get("Census Blocks", [{}])[0]
    addr_components = m.get("addressComponents", {})
    return Address(
        raw=address,
        matched=m["matchedAddress"],
        lat=float(coords["y"]),
        lon=float(coords["x"]),
        state_fips=state["STATE"],
        county_fips=county["COUNTY"],
        tract_fips=tract["TRACT"],
        block_fips=block.get("BLOCK", ""),
        state_abbr=addr_components.get("state", ""),
        county_name=county.get("BASENAME", ""),
        zip=addr_components.get("zip", ""),
    )


def _try_nominatim_fcc(address: str) -> Address | None:
    """Fallback: Nominatim → lat/lon, then FCC Block API → FIPS codes."""
    n_params = {
        "q": address,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 1,
        "countrycodes": "us",
    }
    try:
        n_resp = _retry_get(
            NOMINATIM, params=n_params, headers={"User-Agent": NOMINATIM_UA}
        )
    except RuntimeError:
        return None
    nominatim_results = n_resp.json()
    if not nominatim_results:
        return None
    n = nominatim_results[0]
    lat = float(n["lat"])
    lon = float(n["lon"])
    matched = n.get("display_name", address)
    addr = n.get("address", {})

    # Be polite to Nominatim — they ask for max 1 req/sec.
    time.sleep(1.0)

    f_params = {"latitude": lat, "longitude": lon, "format": "json"}
    try:
        f_resp = _retry_get(FCC_BLOCK, params=f_params)
    except RuntimeError:
        return None
    f = f_resp.json()
    block_info = f.get("Block", {}) or {}
    block_fips_full = block_info.get("FIPS", "")
    if not block_fips_full or len(block_fips_full) < 15:
        return None

    state_fips = block_fips_full[0:2]
    county_fips = block_fips_full[2:5]
    tract_fips = block_fips_full[5:11]
    block_fips = block_fips_full[11:15]

    state_abbr = (f.get("State", {}) or {}).get("code", addr.get("ISO3166-2-lvl4", "")[-2:])
    county_name = (f.get("County", {}) or {}).get("name", addr.get("county", "")).replace(" County", "")
    zip_code = addr.get("postcode", "")

    return Address(
        raw=address,
        matched=matched,
        lat=lat,
        lon=lon,
        state_fips=state_fips,
        county_fips=county_fips,
        tract_fips=tract_fips,
        block_fips=block_fips,
        state_abbr=state_abbr,
        county_name=county_name,
        zip=zip_code,
    )


def geocode(address: str) -> Address:
    """Resolve a free-form US address to a canonical Address with FIPS codes.

    Tries the Census Geocoder first (one call, includes FIPS). Falls back
    to Nominatim + FCC if Census is unreachable. Raises ValueError if no
    geocoder can resolve the address.
    """
    addr = _try_census(address)
    if addr is not None:
        return addr
    addr = _try_nominatim_fcc(address)
    if addr is not None:
        return addr
    raise ValueError(
        f"Could not geocode {address!r} via Census or Nominatim+FCC. "
        "Check the address spelling, or retry later if Census Geocoder is down."
    )
