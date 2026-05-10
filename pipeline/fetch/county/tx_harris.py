"""Harris County, TX — HCAD.

FIPS 48201. Houston, Pasadena, Bellaire, Spring (south).

Note: HCAD has aggressive anti-bot on its public portal at hcad.org
and does not publish a public ArcGIS REST endpoint that supports
spatial point-in-polygon queries against the full tax roll. The
ArcGIS Online `OA_HCAD_noFZ` snapshot exists but its spatial query
returns zero features even on points known to lie inside parcels in
the layer's extent — likely a query-config restriction. Adapter is
registered as unsupported so the pipeline keeps running. Update
`service_url` once a working public endpoint is identified.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


class HarrisTxCAD(TxParcelCAD):
    name = "tx_harris_cad"
    full_county_fips = "48201"
    county_label = "Harris County, TX"
    service_url = ""   # not yet identified — see module docstring


register("48201", HarrisTxCAD)
