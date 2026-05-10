"""Miami-Dade County, FL — Property Appraiser.

FIPS 12086. Miami, Hialeah, Coral Gables, Miami Beach, Doral.
Layer 26 of MD_LandInformation carries the joined parcel + tax roll.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._fl_base import FlParcelCAD


class MiamiDadeFlCAD(FlParcelCAD):
    name = "fl_miami_dade_cad"
    full_county_fips = "12086"
    county_label = "Miami-Dade County, FL"
    service_url = (
        "https://gisweb.miamidade.gov/arcgis/rest/services/MD_LandInformation/"
        "MapServer/26"
    )

    attr_map = {
        "tax_assessed_value":     ["TOTAL_VAL_CUR"],
        "tax_market_value":       ["TOTAL_VAL_CUR"],
        "tax_assessed_year":      ["ASSESSMENT_YEAR_CUR"],
        "owner_name":             ["TRUE_OWNER1"],
        "year_built_cad":         ["YEAR_BUILT"],
        "situs_address":          ["TRUE_SITE_ADDR"],
        # Sale price + date are not exposed on this layer; FL discloses
        # them, but Miami-Dade publishes them via a separate sale-history
        # service that is not part of the joined parcel view.
    }


register("12086", MiamiDadeFlCAD)
