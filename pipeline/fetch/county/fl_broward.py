"""Broward County, FL — Property Appraiser (BCPA).

FIPS 12011. Fort Lauderdale, Hollywood, Pembroke Pines, Coral Springs.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._fl_base import FlParcelCAD


class BrowardFlCAD(FlParcelCAD):
    name = "fl_broward_cad"
    full_county_fips = "12011"
    county_label = "Broward County, FL"
    service_url = (
        "https://gis.broward.org/arcgis/rest/services/Parcels/MapServer/0"
    )


register("12011", BrowardFlCAD)
