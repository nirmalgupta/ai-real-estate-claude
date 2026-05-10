"""Hays County, TX — HaysCAD (hayscad.com).

FIPS 48209. Kyle, San Marcos, Buda, Dripping Springs, Wimberley.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


class HaysTxCAD(TxParcelCAD):
    name = "tx_hays_cad"
    full_county_fips = "48209"
    county_label = "Hays County, TX"
    service_url = (
        "https://services6.arcgis.com/j94FvPaik4etwHFk/arcgis/rest/services/"
        "HaysCADWebService1/FeatureServer/0"
    )

    attr_map = {
        "tax_assessed_value":     ["market"],
        "tax_market_value":       ["market"],
        "tax_assessed_year":      ["owner_tax_yr"],
        "lot_size_acres":         ["legal_acreage"],
        "legal_description":      ["legal_desc"],
        "owner_name":             ["owner_name"],
        "property_id":            ["prop_id_text", "prop_id"],
    }


register("48209", HaysTxCAD)
