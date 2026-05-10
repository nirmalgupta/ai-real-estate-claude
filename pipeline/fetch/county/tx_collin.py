"""Collin County, TX — CCAD (collincad.org).

FIPS 48085. Plano, McKinney, Allen, Frisco (north portion), Wylie.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


class CollinTxCAD(TxParcelCAD):
    name = "tx_collin_cad"
    full_county_fips = "48085"
    county_label = "Collin County, TX"
    service_url = (
        "https://gis.collincountytx.gov/arcgis/rest/services/Parcels/MapServer/0"
    )


register("48085", CollinTxCAD)
