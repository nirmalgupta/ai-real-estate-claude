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
        "https://gis.fortbendcountytx.gov/arcgis/rest/services/Parcels/MapServer/0"
    )


register("48157", FortBendTxCAD)
