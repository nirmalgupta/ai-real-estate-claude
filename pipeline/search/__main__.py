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
from pipeline.search.rent import (
    RentBenchmark,
    compute_rent_metrics,
    estimate_rent,
    fetch_rent_benchmark,
)


def _resolve_center(query: str):
    """Turn a free-form query into (lat, lon, label, address_or_None).

    Returning the Address (when geocoded) gives the caller access to
    state/county/tract FIPS for downstream enrichment (e.g. rent comps).
    Raw lat,lon queries skip geocoding and return None for address.
    """
    m = re.fullmatch(r"\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*", query)
    if m:
        return float(m.group(1)), float(m.group(2)), f"{m.group(1)},{m.group(2)}", None
    addr = geocode(query)
    return addr.lat, addr.lon, addr.matched, addr


def _format_money(n: int | None) -> str:
    return f"${n:,}" if n is not None else "-"


def _format_listing(idx: int, L: Listing, rent: int | None,
                    grm: float | None, cap: float | None,
                    rent_label: str) -> str:
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
        f"    rent:   "
        + (f"${rent}/mo ({rent_label})" if rent else "-"),
        f"    grm:    " + (f"{grm}" if grm is not None else "-"),
        f"    cap:    "
        + (f"{cap * 100:.2f}% (rough, 45% expense ratio)"
           if cap is not None else "-"),
        f"    type:   {L.property_type or '-'}",
        f"    mls:    {L.mls_number or '-'}",
    ]
    return "\n".join(lines)


def _rank_key_dollar_per_sqft(L: Listing, _rent, _grm, _cap):
    return (L.price_per_sqft or 10**9, -(L.sqft or 0))


def _rank_key_grm(L: Listing, _rent, grm, _cap):
    # Lowest GRM is best for rentals; None sinks to the bottom
    return (grm if grm is not None else 10**9, L.price or 10**9)


def _rank_key_cap(L: Listing, _rent, _grm, cap):
    # Highest cap rate is best; None sinks
    return (-(cap or -1), L.price or 10**9)


def _rank_key_price(L: Listing, *_):
    return (L.price or 10**9,)


_RANK_KEYS = {
    "dollar_per_sqft": _rank_key_dollar_per_sqft,
    "grm": _rank_key_grm,
    "cap": _rank_key_cap,
    "price": _rank_key_price,
}


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
    p.add_argument("--no-rent", action="store_true",
                   help="Skip rent / GRM / cap-rate enrichment "
                        "(default: enrichment on; uses HUD FMR or ACS).")
    p.add_argument("--sort", choices=list(_RANK_KEYS.keys()),
                   default="dollar_per_sqft",
                   help="Sort order (default: dollar_per_sqft).")
    args = p.parse_args(argv)

    print(f"[1/3] Resolving search center: {args.query}")
    lat, lon, label, center_addr = _resolve_center(args.query)
    print(f"      center: {lat:.6f}, {lon:.6f} ({label})")
    print(f"      radius: {args.radius} mi")

    print(f"[2/3] Querying Redfin gis-csv...")
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

    # Rent enrichment is on by default per the project's open-source
    # philosophy (free path works without env vars or flags).
    bench: RentBenchmark | None = None
    if not args.no_rent:
        print(f"[3/3] Fetching rent benchmark for search center...")
        if center_addr is not None:
            bench = fetch_rent_benchmark(
                state_fips=center_addr.state_fips,
                county_fips=center_addr.county_fips,
                tract_fips=center_addr.tract_fips,
            )
            print(f"      rent: {bench.note}")
        else:
            print("      skipped — raw lat,lon queries can't resolve county FIPS")
    print()

    # Pre-compute enrichment per listing so the sort key can use it
    enriched: list[tuple[Listing, int | None, float | None,
                         float | None, str]] = []
    for L in listings:
        rent: int | None = None
        rent_label = "-"
        if bench is not None and bench.source != "unavailable":
            est = estimate_rent(L.beds, L.sqft, bench)
            if est:
                rent, rent_label = est
        grm, cap = compute_rent_metrics(L.price, rent)
        enriched.append((L, rent, grm, cap, rent_label))

    sort_key = _RANK_KEYS[args.sort]
    enriched.sort(key=lambda t: sort_key(t[0], t[1], t[2], t[3]))

    for i, (L, rent, grm, cap, rent_label) in enumerate(enriched, start=1):
        print(_format_listing(i, L, rent, grm, cap, rent_label))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
