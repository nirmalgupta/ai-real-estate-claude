"""Durham County, NC — Assessor.

FIPS 37063. Durham proper, parts of RTP.

Note: Durham does not appear to publish a public ArcGIS REST endpoint
for its tax-assessor parcel layer (their public-facing data is HTML at
spatialdata.dconc.gov / dconc.gov tax pages). Adapter is registered
but reports a clean unsupported error so the pipeline keeps running.
Update `service_url` once a public REST endpoint is identified.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._nc_base import NcParcelCAD


class DurhamNcCAD(NcParcelCAD):
    name = "nc_durham_cad"
    full_county_fips = "37063"
    county_label = "Durham County, NC"
    service_url = ""   # not yet identified — see module docstring


register("37063", DurhamNcCAD)
