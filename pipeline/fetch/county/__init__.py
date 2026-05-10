"""County CAD (Central Appraisal District) plug-in registry.

Why this is a registry, not a single fetcher:
    Property assessment in the US is a county function. There are 3,143
    counties using ~30+ different CAD software platforms (TylerTech,
    PACS, Patriot, custom in-house portals, etc). No common schema.

How this works:
    Each county-specific scraper is a small subclass of CountyCADSource
    that knows how to query that county's portal. Adapters register
    themselves keyed by full county FIPS (state + county codes, e.g.
    "48339" for Montgomery County, TX).

    The pipeline calls `get_cad_source(address)` → returns the right
    adapter, or None if no adapter is registered for that county.
    Pipeline runs anyway; the report just notes "no county records used".

Adding a new county:
    1. Write `pipeline/fetch/county/<state>_<name>.py` subclassing
       CountyCADSource.
    2. Call `register("<full_county_fips>", YourAdapterClass)` at module
       import time.
    3. Import the module in this __init__ so registration fires.

Adapter contract:
    Inputs:  Address (with lat/lon, parsed street, zip)
    Outputs: facts about THIS specific property — assessed value, last
             sale price+date, year built, sqft (per CAD), legal description,
             owner name (where public).
    These are authoritative ground truth and override any aggregator data
    when present.
"""
from __future__ import annotations

from typing import Type

from pipeline.common.address import Address
from pipeline.fetch.base import Source

_REGISTRY: dict[str, Type["CountyCADSource"]] = {}


class CountyCADSource(Source):
    """Base class for county Central Appraisal District scrapers."""

    full_county_fips: str = ""        # subclass must set, e.g. "48339"
    county_label: str = ""            # human-readable, e.g. "Montgomery County, TX"


def register(full_county_fips: str, cls: Type[CountyCADSource]) -> None:
    """Register a CAD adapter for a given county FIPS code (state+county)."""
    if not isinstance(full_county_fips, str) or len(full_county_fips) != 5:
        raise ValueError(f"full_county_fips must be a 5-digit string, got {full_county_fips!r}")
    _REGISTRY[full_county_fips] = cls


def get_cad_source(address: Address) -> CountyCADSource | None:
    """Look up the adapter for an address's county. Returns None if unsupported."""
    cls = _REGISTRY.get(address.full_county_fips)
    return cls() if cls else None


def supported_counties() -> list[str]:
    """List all registered county FIPS codes."""
    return sorted(_REGISTRY.keys())


# Import adapter modules so they call register() at import time.
# Each import is best-effort — if a single adapter is broken, others still work.
from pipeline.fetch.county import _adapters  # noqa: E402, F401
