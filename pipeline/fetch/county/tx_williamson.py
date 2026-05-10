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
        "https://gis.wilco.org/arcgis/rest/services/Parcels/MapServer/0"
    )


register("48491", WilliamsonTxCAD)
