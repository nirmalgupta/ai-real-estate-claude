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
        "https://services1.arcgis.com/ZWOoUZbtaYePLlPw/arcgis/rest/services/"
        "Parcels_and_Property_Details_WebMercator/FeatureServer/0"
    )

    attr_map = {
        "tax_assessed_value":     ["ASSESSED_VAL"],
        "tax_market_value":       ["TOTAL_MARKET"],
        "tax_assessed_year":      ["YEAR_ADDED"],
        "lot_size_acres":         ["ACRES"],
        "legal_description":      ["LEGAL1"],
        "owner_name":             ["OWNER_NAME1"],
        "year_built_cad":         ["YRBLT"],
        "last_sale_price":        ["PRICE"],
        "last_sale_date":         ["SALE_DATE"],
        "property_id":            ["PARCEL_NUMBER"],
        "situs_address":          ["SITE_ADDR_STR"],
    }


register("12099", PalmBeachFlCAD)
