"""Galveston County, TX — GCAD.

FIPS 48167. Galveston, Texas City, League City, Friendswood, Dickinson.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


class GalvestonTxCAD(TxParcelCAD):
    name = "tx_galveston_cad"
    full_county_fips = "48167"
    county_label = "Galveston County, TX"
    service_url = (
        "https://gis.galvestoncountytx.gov/arcgis/rest/services/Parcels/MapServer/0"
    )


register("48167", GalvestonTxCAD)
