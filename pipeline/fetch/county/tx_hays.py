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
        "https://gis.hayscountytx.com/arcgis/rest/services/Parcels/MapServer/0"
    )


register("48209", HaysTxCAD)
