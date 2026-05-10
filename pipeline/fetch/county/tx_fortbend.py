"""Fort Bend County, TX — FBCAD.

FIPS 48157. Sugar Land, Katy (south), Missouri City, Stafford.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


class FortBendTxCAD(TxParcelCAD):
    name = "tx_fortbend_cad"
    full_county_fips = "48157"
    county_label = "Fort Bend County, TX"
    service_url = (
        "https://services2.arcgis.com/D4saGHECICkCeoJm/arcgis/rest/services/"
        "FBCAD_Public_Data/FeatureServer/0"
    )

    attr_map = {
        "tax_assessed_value":     ["TOTALVALUE"],
        "tax_market_value":       ["TOTALVALUE"],
        "lot_size_sqft":          ["LANDSQFT"],
        "lot_size_acres":         ["LANDACRES"],
        "legal_description":      ["LEGAL"],
        "owner_name":             ["OWNERNAME"],
        "year_built_cad":         ["YEARBUILT"],
        "living_area_sqft_cad":   ["TOTSQFTLVG"],
        "property_id":            ["PROPNUMBER"],
        "situs_address":          ["SITUS"],
    }


register("48157", FortBendTxCAD)
