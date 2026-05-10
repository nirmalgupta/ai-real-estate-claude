"""Orange County, NC — Tax Administration.

FIPS 37135. Chapel Hill, Carrboro, Hillsborough.

Public path: Orange County publishes its parcel feature service on
ArcGIS Online (per the county tax department's open-data hub).
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._nc_base import NcParcelCAD


class OrangeNcCAD(NcParcelCAD):
    name = "nc_orange_cad"
    full_county_fips = "37135"
    county_label = "Orange County, NC"
    service_url = (
        "https://services5.arcgis.com/VIBXA0MYUeufZ3XC/arcgis/rest/services/"
        "Orange_County_North_Carolina_Parcels_2025/FeatureServer/9"
    )

    attr_map = {
        "tax_assessed_value":     ["VALUATION"],
        "tax_market_value":       ["VALUATION"],
        "lot_size_acres":         ["CALC_ACRES"],
        "legal_description":      ["LEGAL_DESC"],
        "owner_name":             ["OWNER1_LAST"],
        "year_built_cad":         ["YearBlt"],
        "property_id":            ["PIN"],
        "situs_address":          ["ADDRESS1"],
    }


register("37135", OrangeNcCAD)
