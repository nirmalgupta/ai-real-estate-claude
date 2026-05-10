"""Collin County, TX — CCAD (collincad.org).

FIPS 48085. Plano, McKinney, Allen, Frisco (north portion), Wylie.
Public CCAD data is published on ArcGIS Online; layer 4 of the
CCAD_Parcel_Feature_Set service has the joined parcel + appraisal view.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


class CollinTxCAD(TxParcelCAD):
    name = "tx_collin_cad"
    full_county_fips = "48085"
    county_label = "Collin County, TX"
    service_url = (
        "https://services2.arcgis.com/uXyoacYrZTPTKD3R/arcgis/rest/services/"
        "CCAD_Parcel_Feature_Set/FeatureServer/4"
    )

    attr_map = {
        "tax_assessed_value":     ["currValAssessed"],
        "tax_market_value":       ["currValMarket"],
        "tax_appraised_value":    ["currValAppraised"],
        "tax_assessed_year":      ["currValYear", "propYear"],
        "legal_description":      ["legalDescription"],
        "owner_name":             ["ownerName"],
        "year_built_cad":         ["imprvYearBuilt"],
        "property_id":            ["propID", "PROP_ID"],
        "situs_address":          ["situsConcat"],
    }


register("48085", CollinTxCAD)
