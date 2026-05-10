"""Williamson County, TX — WCAD (wcad.org).

FIPS 48491. Round Rock, Cedar Park, Leander, Georgetown, Hutto.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


class WilliamsonTxCAD(TxParcelCAD):
    name = "tx_williamson_cad"
    full_county_fips = "48491"
    county_label = "Williamson County, TX"
    service_url = (
        "https://services1.arcgis.com/Xff0bbfp6vwIWmlU/arcgis/rest/services/"
        "WCAD_Tax_Parcels/FeatureServer/0"
    )

    attr_map = {
        "tax_assessed_value":     ["CNTASSDVAL", "PRVASSDVAL"],
        "tax_market_value":       ["LNDVALUE"],
        "tax_assessed_year":      ["ASSDVALYRCG"],
        "lot_size_acres":         ["AssessedAc"],
        "owner_name":             ["OWNERNME1"],
        "year_built_cad":         ["RESYRBLT"],
        "property_id":            ["PARCELID", "PropertyID", "LOWPARCELID"],
        "situs_address":          ["SITEADDRESS"],
    }


register("48491", WilliamsonTxCAD)
