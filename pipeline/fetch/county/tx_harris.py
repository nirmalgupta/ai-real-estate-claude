"""Harris County, TX — HCAD.

FIPS 48201. Houston, Pasadena, Bellaire, Spring (south).

HCAD has aggressive anti-bot on its public portal. The most reliable
public path is Harris County's GIS open-data ArcGIS service, which
exposes the parcel layer with appraisal attributes joined in.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


class HarrisTxCAD(TxParcelCAD):
    name = "tx_harris_cad"
    full_county_fips = "48201"
    county_label = "Harris County, TX"
    service_url = (
        "https://www.gis.hctx.net/arcgis/rest/services/Parcels/MapServer/0"
    )


register("48201", HarrisTxCAD)
