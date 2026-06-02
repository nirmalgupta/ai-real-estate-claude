"""Harris County, TX — HCAD.

FIPS 48201. Houston, Pasadena, Bellaire, Spring (south).

Public endpoint: the Harris County enterprise GIS publishes the current
HCAD parcel roll (tax year, owner, appraised/market value, land area,
legal description) as a fully public ArcGIS MapServer layer — no token,
spatial point queries supported:

    https://www.gis.hctx.net/arcgis/rest/services/HCAD/Parcels/MapServer/0

Limitation: this layer carries value/owner/legal/lot but NOT year_built
or living area. Those live in a separate 2021 HCAD snapshot
(`geohwp.houstontx.gov/.../Parcels_Historic/FeatureServer/13`, join on
HCAD_NUM == PARCEL_ID) — left as a future enhancement rather than a
second live query per property.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


class HarrisTxCAD(TxParcelCAD):
    name = "tx_harris_cad"
    full_county_fips = "48201"
    county_label = "Harris County, TX"
    service_url = (
        "https://www.gis.hctx.net/arcgis/rest/services/"
        "HCAD/Parcels/MapServer/0"
    )

    attr_map = {
        "tax_assessed_value":  ["total_appraised_val", "tax_value"],
        "tax_market_value":    ["total_market_val"],
        "tax_assessed_year":   ["tax_year"],
        "lot_size_sqft":       ["land_sqft"],
        "lot_size_acres":      ["acreage_1"],
        "legal_description":   ["legal_dscr_1"],
        "owner_name":          ["owner_name_1"],
        "property_id":         ["HCAD_NUM", "acct_num"],
    }


register("48201", HarrisTxCAD)
