"""Palm Beach County, FL — Property Appraiser (PAPA).

FIPS 12099. West Palm Beach, Boca Raton, Boynton Beach, Delray Beach,
Wellington.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._fl_base import FlParcelCAD


class PalmBeachFlCAD(FlParcelCAD):
    name = "fl_palmbeach_cad"
    full_county_fips = "12099"
    county_label = "Palm Beach County, FL"
    service_url = (
        "https://maps.co.palm-beach.fl.us/arcgis/rest/services/Parcels/"
        "MapServer/0"
    )


register("12099", PalmBeachFlCAD)
