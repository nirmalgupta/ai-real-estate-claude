"""Tarrant County, TX — TAD (tad.org).

FIPS 48439. Fort Worth, Arlington, Grand Prairie (west), Mansfield.
TAD historically has heavier anti-bot — the GIS open-data path is the
reliable public option.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


class TarrantTxCAD(TxParcelCAD):
    name = "tx_tarrant_cad"
    full_county_fips = "48439"
    county_label = "Tarrant County, TX"
    service_url = (
        "https://gis.tarrantcounty.com/arcgis/rest/services/Parcels/MapServer/0"
    )


register("48439", TarrantTxCAD)
