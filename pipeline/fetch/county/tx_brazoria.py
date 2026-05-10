"""Brazoria County, TX — BCAD.

FIPS 48039. Pearland, Lake Jackson, Angleton, Alvin.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


class BrazoriaTxCAD(TxParcelCAD):
    name = "tx_brazoria_cad"
    full_county_fips = "48039"
    county_label = "Brazoria County, TX"
    service_url = (
        "https://gis.brazoria-county.com/arcgis/rest/services/Parcels/MapServer/0"
    )


register("48039", BrazoriaTxCAD)
