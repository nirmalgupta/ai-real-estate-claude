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

    # Denton County GIS open-data parcel layer. Note: this URL is the
    # documented public endpoint; if Denton rolls a new layer index the
    # adapter will return a clean error and the pipeline carries on.
    service_url = (
        "https://gis.dentoncounty.gov/server/rest/services/"
        "Parcels/MapServer/0"
    )

    attr_map = {
        # Denton's parcel layer ships several appraisal aliases. Order is
        # most-specific first so the chosen value is the right one.
        "tax_assessed_value":     ["TOTAL_APPRAISED_VALUE", "TOTAL_APPRAISED_VAL", "TOTAL_VAL"],
        "tax_market_value":       ["TOTAL_MARKET_VALUE", "MARKET_VAL"],
        "tax_assessed_year":      ["APPRAISAL_YEAR", "YEAR", "TAX_YEAR"],
        "lot_size_sqft":          ["LAND_SQFT", "GIS_SQFT"],
        "lot_size_acres":         ["LAND_ACRES", "GIS_ACRES", "ACRES"],
        "legal_description":      ["LEGAL_DESC", "LEGAL", "LEGAL_LINE_1"],
        "owner_name":             ["OWNER_NAME", "OWNER"],
        "last_deed_date":         ["DEED_DATE", "TRANSFER_DATE"],
        "year_built_cad":         ["YEAR_BUILT", "ACTUAL_YEAR_BUILT"],
        "living_area_sqft_cad":   ["LIVING_AREA", "LIVING_SQFT", "TOTAL_SF"],
        "property_id":            ["PROP_ID", "PROPERTY_ID", "PIN", "ACCOUNT_NUM"],
    }


register("48121", DentonTxCAD)
