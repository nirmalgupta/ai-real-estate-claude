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
from pipeline.fetch.bea_regional import BeaRegionalSource
from pipeline.fetch.bls_laus import BlsLausSource
from pipeline.fetch.census_acs import CensusACSSource
from pipeline.fetch.county import get_cad_source, supported_counties
from pipeline.fetch.fema_nfhl import FemaNFHLSource
from pipeline.fetch.fema_nfip import FemaNfipSource
from pipeline.fetch.hud_fmr import HudFmrSource
from pipeline.fetch.movoto import MovotoSource
from pipeline.fetch.nces import NCESSource
from pipeline.fetch.noaa_normals import NoaaNormalsSource
from pipeline.fetch.noaa_spc import NoaaSpcSource
from pipeline.fetch.osm_amenities import OsmAmenitiesSource
from pipeline.fetch.redfin import RedfinSource
from pipeline.fetch.redfin_comps import RedfinCompsSource
from pipeline.fetch.usgs_eq import UsgsEqSource
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
        help="Optional Movoto listing URL — only useful when Redfin doesn't "
             "carry the listing. No auto-discovery; supply the URL yourself.",
    )
    p.add_argument(
        "--redfin-url",
        default=None,
        help="Optional Redfin listing URL for deep per-property research. "
             "Use `python3 -m pipeline.search` to find candidates first.",
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
        FemaNfipSource(),
        CensusACSSource(),
        HudFmrSource(),
        NCESSource(),
        NoaaSpcSource(),
        NoaaNormalsSource(),
        UsgsEqSource(),
        OsmAmenitiesSource(),
        BlsLausSource(),
        BeaRegionalSource(),
        MovotoSource(listing_url=args.movoto_url),
        RedfinSource(listing_url=args.redfin_url),
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

    # Sold-comps lookup runs last because it needs sqft/beds/type from
    # earlier fetchers (Redfin / CAD). Skip if we don't have enough to
    # filter — running the strict-radius query without a sqft anchor
    # would return random nearby sales.
    facts_so_far: dict = {}
    for r in results:
        for k, fact in r.facts.items():
            facts_so_far.setdefault(k, fact.value)
    subject_sqft = (
        facts_so_far.get("living_area_sqft_listing")
        or facts_so_far.get("sqft")
        or facts_so_far.get("living_area")
    )
    subject_beds = facts_so_far.get("beds")
    subject_type = (
        facts_so_far.get("property_type_redfin") or facts_so_far.get("property_type")
    )
    if subject_sqft and subject_beds:
        print(f"      - redfin_comps...", end=" ", flush=True)
        rc = RedfinCompsSource(
            subject_sqft=int(subject_sqft) if subject_sqft else None,
            subject_beds=int(subject_beds) if subject_beds else None,
            subject_type=subject_type,
        ).fetch(addr)
        if rc.ok:
            print(f"ok ({len(rc.facts)} fact(s))")
        else:
            print(f"FAILED: {rc.error}")
        results.append(rc)
    else:
        print("      - redfin_comps... skipped (need sqft + beds from earlier fetchers)")

    print(f"[3/3] Writing wiki page to {args.wiki}/properties/{addr.slug}.md")
    out = write_page(addr, results, args.wiki)
    print(f"      wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
