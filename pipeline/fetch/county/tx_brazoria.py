"""Brazoria County, TX — BCAD.

FIPS 48039. Pearland, Lake Jackson, Angleton, Alvin.

Public path: the Texas StratMap statewide land-parcels feature service
(per-county slice 48039). Maintained by TNRIS / Rice University.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


class BrazoriaTxCAD(TxParcelCAD):
    name = "tx_brazoria_cad"
    full_county_fips = "48039"
    county_label = "Brazoria County, TX"
    service_url = (
        "https://services.arcgis.com/lqRTrQp2HrfnJt8U/arcgis/rest/services/"
        "stratmap22_landparcels_48039_lp/FeatureServer/0"
    )

    attr_map = {
        "tax_assessed_value":     ["MKT_VALUE"],
        "tax_market_value":       ["MKT_VALUE"],
        "tax_assessed_year":      ["TAX_YEAR"],
        "legal_description":      ["LEGAL_DESC"],
        "owner_name":             ["OWNER_NAME"],
        "year_built_cad":         ["YEAR_BUILT"],
        "property_id":            ["Prop_ID"],
        "situs_address":          ["SITUS_ADDR"],
    }


register("48039", BrazoriaTxCAD)
