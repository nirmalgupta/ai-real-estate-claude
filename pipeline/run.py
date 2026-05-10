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
from pipeline.fetch.county import get_cad_source, supported_counties
from pipeline.fetch.fema_nfhl import FemaNFHLSource
from pipeline.fetch.hud_fmr import HudFmrSource
from pipeline.fetch.movoto import MovotoSource
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
    p.add_argument(
        "--movoto-url",
        default=None,
        help="Optional Movoto listing URL to use directly. Bypasses search "
             "(which is unreliable). Find via Google `site:movoto.com \"<address>\"`.",
    )
    args = p.parse_args(argv)

    print(f"[1/3] Geocoding: {args.address}")
    addr = geocode(args.address)
    print(f"      matched: {addr.matched}")
    print(f"      lat/lon: {addr.lat}, {addr.lon}")
    print(f"      tract:   {addr.full_tract_fips}  ({addr.county_name} County, {addr.state_abbr})")

    print("[2/3] Fetching sources...")
    sources = [
        FemaNFHLSource(),
        CensusACSSource(),
        HudFmrSource(),
        MovotoSource(listing_url=args.movoto_url),
    ]

    # County CAD adapter is plug-in: included only if registered for this
    # county. The pipeline runs fine without one.
    cad = get_cad_source(addr)
    if cad is not None:
        sources.append(cad)
        print(f"      (CAD adapter registered for {addr.full_county_fips}: {cad.name})")
    else:
        registered = supported_counties()
        if registered:
            print(f"      (no CAD adapter for {addr.full_county_fips}; "
                  f"registered: {', '.join(registered)})")
        else:
            print("      (no CAD adapters registered yet — county records skipped)")

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
