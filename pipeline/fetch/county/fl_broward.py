"""Broward County, FL — Property Appraiser (BCPA).

FIPS 12011. Fort Lauderdale, Hollywood, Pembroke Pines, Coral Springs.
The joined parcel + tax roll lives at PARCEL_POLY_BCPA_TAXROLL/0.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._fl_base import FlParcelCAD


class BrowardFlCAD(FlParcelCAD):
    name = "fl_broward_cad"
    full_county_fips = "12011"
    county_label = "Broward County, FL"
    service_url = (
        "https://services.arcgis.com/JMAJrTsHNLrSsWf5/arcgis/rest/services/"
        "PARCEL_POLY_BCPA_TAXROLL/FeatureServer/0"
    )

    attr_map = {
        # Broward exposes the breakdown of just-value (FL's "market"
        # equivalent) and the prior-year assessed total.
        "tax_market_value":       ["LY_JUSTVAL"],
        "tax_assessed_value":     ["LAST_YRS_ASSESSED"],
        "tax_assessed_year":      ["SOH_YEAR"],
        "legal_description":      ["LEGAL_LINE_1"],
        "year_built_cad":         ["BLDG_YEAR_BUILT", "ACTUAL_YEAR_BUILT"],
        "last_sale_date":         ["SALE_DATE_1"],
        "last_sale_price":        ["SALE_VER1"],   # SALE_VER1 is the verified sale price
        "situs_address":          ["SITUS_STREET_NAME"],
    }


register("12011", BrowardFlCAD)
