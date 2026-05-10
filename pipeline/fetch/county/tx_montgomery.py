"""Montgomery County, TX — MCAD.

FIPS 48339. The Woodlands, Conroe, Spring (north), Magnolia. Test
address: 31 Glenleigh Pl, The Woodlands.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


class MontgomeryTxCAD(TxParcelCAD):
    name = "tx_montgomery_cad"
    full_county_fips = "48339"
    county_label = "Montgomery County, TX"
    service_url = (
        "https://gis.mctx.org/arcgis/rest/services/Parcels/MapServer/0"
    )


register("48339", MontgomeryTxCAD)
