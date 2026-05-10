"""OpenStreetMap amenities fetcher.

Returns the nearest commercial amenities for a property — groceries,
pharmacies, restaurants — via the Overpass API.

Why this matters for an investment-property tool:
    - "Walk to grocery" is a major rent / resale driver.
    - Distance to the nearest supermarket is a useful neighborhood-tier
      signal: <0.5 mi = urban infill, 0.5–2 mi = suburban, >5 mi = rural.
    - Pharmacy + restaurant density rounds out "is this a real
      neighborhood or a subdivision island."

Source: Overpass API (https://overpass-api.de/api/interpreter). Free,
no key, returns OSM nodes/ways/relations matching tag filters. We use
the documented `shop=supermarket`, `shop=convenience`, `amenity=pharmacy`,
`amenity=restaurant` tag patterns.

Overpass etiquette: cap to one query per fetch, set a 25-second timeout
server-side. Self-hosting is the right move if this ever ships in
volume.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import httpx

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult, Source

OVERPASS = "https://overpass-api.de/api/interpreter"

SEARCH_RADIUS_METERS = 4828   # ~3 miles
MAX_RESULTS_PER_KIND = 5


@dataclass
class _OsmKind:
    """One category we query in a single Overpass round-trip."""
    fact_key: str
    label: str                       # human-readable in the wiki
    tag_filter: str                  # Overpass tag expression


# The categories we surface. Order is what goes into the wiki frontmatter
# under their respective keys.
KINDS = [
    _OsmKind("nearest_supermarkets", "Supermarket / large grocer",
             '"shop"="supermarket"'),
    _OsmKind("nearest_convenience_stores", "Convenience / corner store",
             '"shop"="convenience"'),
    _OsmKind("nearest_pharmacies", "Pharmacy",
             '"amenity"="pharmacy"'),
    _OsmKind("nearest_restaurants", "Restaurant",
             '"amenity"="restaurant"'),
]


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3958.7613
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _build_query(lat: float, lon: float) -> str:
    """One Overpass QL query covering all categories.

    Using `out center` collapses ways/relations to a single lat/lon point
    so we can rank by haversine distance without polygon math.
    """
    parts = []
    for k in KINDS:
        parts.append(
            f"nwr[{k.tag_filter}](around:{SEARCH_RADIUS_METERS},{lat},{lon});"
        )
    body = "\n".join(parts)
    return (
        f"[out:json][timeout:25];\n"
        f"(\n{body}\n);\n"
        f"out center {MAX_RESULTS_PER_KIND * len(KINDS) * 4};\n"
    )


def _element_latlon(elem: dict) -> tuple[float, float] | None:
    """OSM nodes carry lat/lon directly; ways/relations only carry it
    when we ask for `out center`. Pull whichever exists."""
    if "lat" in elem and "lon" in elem:
        return float(elem["lat"]), float(elem["lon"])
    center = elem.get("center")
    if isinstance(center, dict) and "lat" in center and "lon" in center:
        return float(center["lat"]), float(center["lon"])
    return None


def _classify_element(tags: dict) -> str | None:
    """Map an element's tags to one of our KIND.fact_key buckets."""
    if tags.get("shop") == "supermarket":
        return "nearest_supermarkets"
    if tags.get("shop") == "convenience":
        return "nearest_convenience_stores"
    if tags.get("amenity") == "pharmacy":
        return "nearest_pharmacies"
    if tags.get("amenity") == "restaurant":
        return "nearest_restaurants"
    return None


class OsmAmenitiesSource(Source):
    name = "osm_amenities"

    def fetch(self, address: Address) -> FetchResult:
        query = _build_query(address.lat, address.lon)
        try:
            r = httpx.post(
                OVERPASS, data={"data": query}, timeout=45.0,
                headers={"User-Agent": "ai-real-estate-pipeline/0.2"},
            )
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as e:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"Overpass request failed: {e}",
            )

        elements = data.get("elements") or []

        # Group by category, ranked by distance.
        by_key: dict[str, list[dict]] = {k.fact_key: [] for k in KINDS}
        for elem in elements:
            tags = elem.get("tags") or {}
            key = _classify_element(tags)
            if key is None:
                continue
            ll = _element_latlon(elem)
            if ll is None:
                continue
            dist = _haversine_miles(address.lat, address.lon, ll[0], ll[1])
            by_key[key].append({
                "name": tags.get("name") or tags.get("operator") or "(unnamed)",
                "brand": tags.get("brand"),
                "distance_miles": round(dist, 2),
                "lat": ll[0],
                "lon": ll[1],
                "osm_id": elem.get("id"),
                "osm_type": elem.get("type"),
            })

        for k in by_key:
            by_key[k].sort(key=lambda e: e["distance_miles"])
            by_key[k] = by_key[k][:MAX_RESULTS_PER_KIND]

        facts: dict[str, Fact] = {}
        ref = f"{OVERPASS} (around:{SEARCH_RADIUS_METERS}m, {address.lat:.4f},{address.lon:.4f})"
        for k in KINDS:
            results = by_key[k.fact_key]
            if results:
                facts[k.fact_key] = Fact(
                    value=results, source=self.name, raw_ref=ref,
                    note=f"{k.label} within "
                         f"{SEARCH_RADIUS_METERS/1609:.1f} mi, nearest first",
                )
                # Companion convenience fact: just the nearest distance.
                facts[f"{k.fact_key}_nearest_miles"] = Fact(
                    value=results[0]["distance_miles"],
                    source=self.name, raw_ref=ref,
                )

        if not facts:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error="OSM Overpass returned no matching amenities within "
                      f"{SEARCH_RADIUS_METERS/1609:.1f} miles.",
            )

        return FetchResult(
            source_name=self.name, address=address, facts=facts,
            raw={"element_count": len(elements)},
        )
