"""Johnston County, NC — Tax Office.

FIPS 37101. Smithfield, Clayton, Garner (south), Selma, Benson.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._nc_base import NcParcelCAD


class JohnstonNcCAD(NcParcelCAD):
    name = "nc_johnston_cad"
    full_county_fips = "37101"
    county_label = "Johnston County, NC"
    service_url = (
        "https://gis.johnstonnc.com/arcgis/rest/services/Parcels/MapServer/0"
    )


register("37101", JohnstonNcCAD)
