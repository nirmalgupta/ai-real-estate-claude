"""Travis County, TX — TCAD (traviscad.org).

FIPS 48453. Austin proper, Pflugerville (south), West Lake Hills.
TCAD has anti-bot on its property-search portal; the GIS open-data
ArcGIS service is the dependable public path.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


class TravisTxCAD(TxParcelCAD):
    name = "tx_travis_cad"
    full_county_fips = "48453"
    county_label = "Travis County, TX"
    service_url = (
        "https://services.arcgis.com/0L95CJ0VTaxqcmED/arcgis/rest/services/"
        "Travis_County_Parcels/FeatureServer/0"
    )


register("48453", TravisTxCAD)
