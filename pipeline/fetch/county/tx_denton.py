"""Denton County, TX — Central Appraisal District (DCAD).

FIPS 48121. Covers Denton, Lewisville, Frisco (south part), Flower Mound,
Little Elm, The Colony, Argyle.

Data path:
    Denton County GIS publishes a parcel feature service via ArcGIS REST.
    DCAD's appraisal data is joined onto parcel polygons in the county's
    open-data layer. We hit the parcel layer with a point-in-polygon
    query at the property's lat/lon and pull the appraisal attributes.

TX non-disclosure:
    Texas does NOT publish sale prices in CAD records — only the deed
    transfer date. `last_sale_price` is therefore intentionally omitted.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._arcgis import ArcGISParcelCAD


class DentonTxCAD(ArcGISParcelCAD):
    name = "tx_denton_cad"
    full_county_fips = "48121"
    county_label = "Denton County, TX"
    sale_price_disclosed = False

    # Denton County GIS publishes the joined CAD layer at
    #   /arcgis/rest/services/CAD/MapServer/0  (parcel polygons).
    # Field names are lowercase. Confirmed live against
    # 6919 Tailwater Trl, Frisco — 2026-05.
    service_url = (
        "https://gis.dentoncounty.gov/arcgis/rest/services/CAD/MapServer/0"
    )

    attr_map = {
        "tax_assessed_value":     ["cert_asses_val", "asses_val"],
        "tax_market_value":       ["cert_mkt_val", "mkt_val"],
        "tax_appraised_value":    ["cert_appr_val", "appr_val"],
        "tax_assessed_year":      ["prop_val_yr"],
        "lot_size_sqft":          ["land_sqft"],
        "lot_size_acres":         ["legal_acreage"],
        "legal_description":      ["legal_desc"],
        "owner_name":             ["owner_name"],
        # Denton's CAD layer does not publish a transfer date column;
        # deedID/volume/page are the only deed pointers and aren't
        # dates, so we omit last_deed_date here. (TX is non-disclosure
        # state, so last_sale_price is also not exposed.)
        "year_built_cad":         ["yr_blt"],
        "living_area_sqft_cad":   ["living_area"],
        "property_id":            ["prop_id", "PID"],
        "situs_address":          ["situs"],
    }


register("48121", DentonTxCAD)
