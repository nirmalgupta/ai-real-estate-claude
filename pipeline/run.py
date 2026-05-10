"""CLI entry point.

Usage:
    python -m pipeline.run "31 Glenleigh Pl, The Woodlands, TX 77381"

Phase 1: geocode → run all national fetchers → write wiki page.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline.common.address import geocode
from pipeline.fetch.census_acs import CensusACSSource
from pipeline.fetch.fema_nfhl import FemaNFHLSource
from pipeline.wiki.builder import write_page

DEFAULT_WIKI_ROOT = Path(__file__).resolve().parent.parent / "wiki"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run the AI real-estate pipeline on one address.")
    p.add_argument("address", help="Free-form US address")
    p.add_argument(
        "--wiki",
        type=Path,
        default=DEFAULT_WIKI_ROOT,
        help="Wiki root directory (default: ./wiki)",
    )
    args = p.parse_args(argv)

    print(f"[1/3] Geocoding: {args.address}")
    addr = geocode(args.address)
    print(f"      matched: {addr.matched}")
    print(f"      lat/lon: {addr.lat}, {addr.lon}")
    print(f"      tract:   {addr.full_tract_fips}  ({addr.county_name} County, {addr.state_abbr})")

    print("[2/3] Fetching national sources...")
    sources = [FemaNFHLSource(), CensusACSSource()]
    results = []
    for s in sources:
        print(f"      - {s.name}...", end=" ", flush=True)
        r = s.fetch(addr)
        if r.ok:
            print(f"ok ({len(r.facts)} fact(s))")
        else:
            print(f"FAILED: {r.error}")
        results.append(r)

    print(f"[3/3] Writing wiki page to {args.wiki}/properties/{addr.slug}.md")
    out = write_page(addr, results, args.wiki)
    print(f"      wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
