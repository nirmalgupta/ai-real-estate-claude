"""Dallas County, TX — DCAD parcels.

FIPS 48113. Dallas, Irving, Mesquite, Garland, Richardson (south).

Note: Dallas County's public ArcGIS feature service publishes parcel
polygons + owner + legal description but NOT appraisal values. The web
property-search portal at https://www.dallascad.org/ has values, but it
is HTML-only and not exposed as JSON. We surface what's available.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


class DallasTxCAD(TxParcelCAD):
    name = "tx_dallas_cad"
    full_county_fips = "48113"
    county_label = "Dallas County, TX"
    service_url = (
        "https://services2.arcgis.com/rwnOSbfKSwyTBcwN/arcgis/rest/services/"
        "DallasTaxParcels/FeatureServer/0"
    )

    attr_map = {
        # DCAD's public parcel layer ships polygons + owner + legal only
        # (appraised values are paywalled / HTML-only). We surface what's
        # available; the assessed-value Fact will simply be missing.
        "tax_assessed_year":      ["APPRAISALYEAR"],
        "legal_description":      ["LEGAL_1"],
        "owner_name":             ["TAXPANAME1"],
        "property_id":            ["ACCT", "GIS_ACCT"],
        "situs_address":          ["ST_NUM", "ST_NAME"],
    }


register("48113", DallasTxCAD)
