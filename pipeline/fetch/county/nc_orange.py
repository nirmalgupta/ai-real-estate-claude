"""Orange County, NC — Tax Administration.

FIPS 37135. Chapel Hill, Carrboro, Hillsborough.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._nc_base import NcParcelCAD


class OrangeNcCAD(NcParcelCAD):
    name = "nc_orange_cad"
    full_county_fips = "37135"
    county_label = "Orange County, NC"
    service_url = (
        "https://gis.orangecountync.gov/arcgis/rest/services/Parcels/MapServer/0"
    )


register("37135", OrangeNcCAD)
