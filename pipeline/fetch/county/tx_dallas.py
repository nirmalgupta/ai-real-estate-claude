"""Dallas County, TX — DCAD (dallascad.org).

FIPS 48113. Dallas, Irving, Mesquite, Garland, Richardson (south).
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


class DallasTxCAD(TxParcelCAD):
    name = "tx_dallas_cad"
    full_county_fips = "48113"
    county_label = "Dallas County, TX"
    service_url = (
        "https://gis.dallascounty.org/arcgis/rest/services/Parcels/MapServer/0"
    )


register("48113", DallasTxCAD)
