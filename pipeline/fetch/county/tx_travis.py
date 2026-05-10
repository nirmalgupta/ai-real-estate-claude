"""Travis County, TX — TCAD (traviscad.org).

FIPS 48453. Austin proper, Pflugerville (south), West Lake Hills.
TCAD's public ArcGIS Online feature service publishes the parcel
polygons with limited appraisal data (LAND_VALUE only — improvement
and total values aren't surfaced on the public layer).
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
        "EXTERNAL_tcad_parcel/FeatureServer/0"
    )

    attr_map = {
        # TCAD's public layer is partial — only land value, no
        # improvements / total / owner / sale history are exposed.
        "tax_market_value":       ["LAND_VALUE"],
        "property_id":            ["PROP_ID"],
        "situs_address":          ["SITUS"],
    }


register("48453", TravisTxCAD)
