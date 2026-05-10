"""Wake County, NC — Tax Administration / iMAPS.

FIPS 37183. Raleigh, Cary, Apex, Wake Forest, Garner, Holly Springs.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._nc_base import NcParcelCAD


class WakeNcCAD(NcParcelCAD):
    name = "nc_wake_cad"
    full_county_fips = "37183"
    county_label = "Wake County, NC"
    service_url = (
        "https://maps.wakegov.com/arcgis/rest/services/Property/Parcels/"
        "MapServer/0"
    )

    attr_map = {
        "tax_assessed_value":     ["TOTAL_VALUE_ASSD"],
        "tax_market_value":       ["TOTAL_VALUE_ASSD"],
        "lot_size_acres":         ["DEED_ACRES"],
        "legal_description":      ["PROPDESC"],
        "owner_name":             ["OWNER"],
        "year_built_cad":         ["YEAR_BUILT"],
        "last_sale_price":        ["TOTSALPRICE"],
        "last_sale_date":         ["SALE_DATE"],
        "property_id":            ["PIN_NUM", "PARCEL_PK"],
        "situs_address":          ["SITE_ADDRESS"],
    }


register("37183", WakeNcCAD)
