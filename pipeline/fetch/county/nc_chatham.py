"""Chatham County, NC — Tax Office.

FIPS 37037. Pittsboro, Siler City, Goldston.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._nc_base import NcParcelCAD


class ChathamNcCAD(NcParcelCAD):
    name = "nc_chatham_cad"
    full_county_fips = "37037"
    county_label = "Chatham County, NC"
    service_url = (
        "https://gis.chathamcountync.gov/arcgis/rest/services/Parcels/MapServer/0"
    )


register("37037", ChathamNcCAD)
