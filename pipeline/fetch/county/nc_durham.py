"""Durham County, NC — Assessor.

FIPS 37063. Durham proper, parts of RTP.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._nc_base import NcParcelCAD


class DurhamNcCAD(NcParcelCAD):
    name = "nc_durham_cad"
    full_county_fips = "37063"
    county_label = "Durham County, NC"
    service_url = (
        "https://gisweb.durhamnc.gov/arcgis/rest/services/Parcels/MapServer/0"
    )


register("37063", DurhamNcCAD)
