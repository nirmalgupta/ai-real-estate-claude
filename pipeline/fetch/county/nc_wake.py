"""Wake County, NC — Tax Administration / iMAPS.

FIPS 37183. Raleigh, Cary, Apex, Wake Forest, Garner, Holly Springs.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._nc_base import NcParcelCAD


class WakeNcCAD(NcParcelCAD):
    name = "nc_wake_cad"
    full_county_fips = "37183"
    county_label = "Wake County, NC"
    service_url = (
        "https://maps.wake.gov/arcgis/rest/services/Property/Property/MapServer/0"
    )


register("37183", WakeNcCAD)
