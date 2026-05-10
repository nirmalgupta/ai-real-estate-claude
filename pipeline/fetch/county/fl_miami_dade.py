"""Miami-Dade County, FL — Property Appraiser.

FIPS 12086. Miami, Hialeah, Coral Gables, Miami Beach, Doral.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._fl_base import FlParcelCAD


class MiamiDadeFlCAD(FlParcelCAD):
    name = "fl_miami_dade_cad"
    full_county_fips = "12086"
    county_label = "Miami-Dade County, FL"
    service_url = (
        "https://gisweb.miamidade.gov/arcgis/rest/services/MD_PropertySearch/"
        "MapServer/0"
    )


register("12086", MiamiDadeFlCAD)
