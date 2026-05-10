"""Johnston County, NC — Tax Office.

FIPS 37101. Smithfield, Clayton, Garner (south), Selma, Benson.
Snapshot of the 2020 tax-roll parcels published on ArcGIS Online.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._nc_base import NcParcelCAD


class JohnstonNcCAD(NcParcelCAD):
    name = "nc_johnston_cad"
    full_county_fips = "37101"
    county_label = "Johnston County, NC"
    service_url = (
        "https://services.arcgis.com/rD2ylXRs80UroD90/arcgis/rest/services/"
        "Johnston_County_NC_Parcels_2020/FeatureServer/0"
    )

    attr_map = {
        "tax_assessed_value":     ["TOT_VALUE"],
        "tax_market_value":       ["MARKET_VAL"],
        "legal_description":      ["LEGAL"],
        "year_built_cad":         ["YEAR_BUILT"],
        "last_sale_price":        ["SALES_PRIC"],
        "last_sale_date":         ["SALES_DATE"],
        "property_id":            ["PIN"],
        "situs_address":          ["ADDRESS1"],
    }


register("37101", JohnstonNcCAD)
