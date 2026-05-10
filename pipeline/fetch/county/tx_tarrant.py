"""Tarrant County, TX — TAD (tad.org).

FIPS 48439. Fort Worth, Arlington, Grand Prairie (west), Mansfield.

Note: TAD does not publish a public ArcGIS REST endpoint with all
appraisal-district parcels. The county's `mapit.tarrantcounty.com`
service exposes only county-government-owned parcels (~3 records),
not the full tax roll. The standard public access is the HTML portal
at tad.org, which doesn't return JSON. Adapter is registered as
unsupported so the pipeline keeps running. Update `service_url` once
a public REST endpoint is identified.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


class TarrantTxCAD(TxParcelCAD):
    name = "tx_tarrant_cad"
    full_county_fips = "48439"
    county_label = "Tarrant County, TX"
    service_url = ""   # not yet identified — see module docstring


register("48439", TarrantTxCAD)
