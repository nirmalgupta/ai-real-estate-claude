"""Chatham County, NC — Tax Office.

FIPS 37037. Pittsboro, Siler City, Goldston.

Note: Chatham's GIS server publishes tax-foreclosure and zoning layers
publicly, but the joined parcel + appraisal layer is not exposed at a
stable JSON endpoint that the smoke probe could verify. Adapter is
registered as unsupported so the pipeline keeps running. Update
`service_url` once a public REST endpoint is identified.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._nc_base import NcParcelCAD


class ChathamNcCAD(NcParcelCAD):
    name = "nc_chatham_cad"
    full_county_fips = "37037"
    county_label = "Chatham County, NC"
    service_url = ""   # not yet identified — see module docstring


register("37037", ChathamNcCAD)
