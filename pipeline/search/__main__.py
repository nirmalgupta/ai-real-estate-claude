"""CLI entry point for multi-property search.

Examples:
    python3 -m pipeline.search "Frisco, TX"
    python3 -m pipeline.search "Frisco, TX" --radius 5 --max-price 600000 --min-beds 3
    python3 -m pipeline.search "75036" --radius 2
    python3 -m pipeline.search "33.136,-96.889" --radius 1     # raw lat,lon

Output: one key:value block per listing, ranked by best $/sqft. Designed
so the user can scan the list, pick promising candidates, and run the
full per-property `pipeline.run` on each.
"""
from __future__ import annotations

import argparse
import re
import sys

from pipeline.common.address import geocode
from pipeline.search.redfin import (
    DEFAULT_PROPERTY_TYPES,
    Listing,
    STATUS_ACTIVE,
    search_redfin,
)


def _resolve_center(query: str) -> tuple[float, float, str]:
    """Turn a free-form query into (lat, lon, label).

    Accepts:
      - 'lat,lon'   raw decimal pair
      - any string the existing geocoder can resolve (city, zip, full address)
    """
    m = re.fullmatch(r"\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*", query)
    if m:
        return float(m.group(1)), float(m.group(2)), f"{m.group(1)},{m.group(2)}"
    addr = geocode(query)
    return addr.lat, addr.lon, addr.matched


def _format_money(n: int | None) -> str:
    return f"${n:,}" if n is not None else "-"


def _format_listing(idx: int, L: Listing) -> str:
    lines = [
        f"[{idx}] {L.display_addr}",
        f"    url:    {L.url or '-'}",
        f"    price:  {_format_money(L.price)}",
        f"    beds:   {L.beds if L.beds is not None else '-'}",
        f"    baths:  {L.baths if L.baths is not None else '-'}",
        f"    sqft:   {L.sqft:,}" if L.sqft else "    sqft:   -",
        f"    lot:    {L.lot_sqft:,} sqft" if L.lot_sqft else "    lot:    -",
        f"    year:   {L.year_built or '-'}",
        f"    hoa:    " + (f"${L.hoa_monthly}/mo" if L.hoa_monthly else "-"),
        f"    dom:    {L.days_on_market} days" if L.days_on_market is not None else "    dom:    -",
        f"    $/sqft: {_format_money(L.price_per_sqft)}",
        f"    type:   {L.property_type or '-'}",
        f"    mls:    {L.mls_number or '-'}",
    ]
    return "\n".join(lines)


def _rank_key(L: Listing) -> tuple[int, int]:
    """Sort: lowest $/sqft first, then highest sqft. Listings missing
    $/sqft sink to the bottom."""
    return (L.price_per_sqft or 10**9, -(L.sqft or 0))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Search active listings in a city / zip / lat-lon area "
                    "and emit a key:value summary per candidate."
    )
    p.add_argument("query", help="Free-form: city, zip, full address, or 'lat,lon'.")
    p.add_argument("--radius", type=float, default=3.0,
                   help="Search radius in miles around the resolved center (default 3).")
    p.add_argument("--max-results", type=int, default=50,
                   help="Max listings to fetch (default 50, Redfin caps at 350).")
    p.add_argument("--min-price", type=int, default=None)
    p.add_argument("--max-price", type=int, default=None)
    p.add_argument("--min-beds", type=int, default=None)
    p.add_argument("--min-baths", type=float, default=None)
    p.add_argument("--property-types", default=DEFAULT_PROPERTY_TYPES,
                   help="Comma-separated Redfin uipt codes (1=house, 2=condo, "
                        "3=townhouse, 4=multi-family, 5=land, 6=other, "
                        "7=mobile, 8=co-op). Default: 1,2,3,4.")
    args = p.parse_args(argv)

    print(f"[1/2] Resolving search center: {args.query}")
    lat, lon, label = _resolve_center(args.query)
    print(f"      center: {lat:.6f}, {lon:.6f} ({label})")
    print(f"      radius: {args.radius} mi")

    print(f"[2/2] Querying Redfin gis-csv...")
    listings, url = search_redfin(
        center_lat=lat,
        center_lon=lon,
        radius_miles=args.radius,
        max_results=args.max_results,
        min_price=args.min_price,
        max_price=args.max_price,
        min_beds=args.min_beds,
        min_baths=args.min_baths,
        property_types=args.property_types,
        status=STATUS_ACTIVE,
    )
    print(f"      {len(listings)} listing(s) after filters")
    print()

    if not listings:
        print("No listings matched. Try widening the radius or relaxing filters.")
        return 0

    listings.sort(key=_rank_key)
    for i, L in enumerate(listings, start=1):
        print(_format_listing(i, L))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
