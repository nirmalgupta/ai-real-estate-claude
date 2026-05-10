"""Shared NC-CAD defaults.

North Carolina is a disclosure state — sale prices and deed details are
public record. Most NC counties run their parcel data on a regional GIS
platform (commonly iMaps or a TylerTech derivative) with overlapping
attribute names.
"""
from __future__ import annotations

from pipeline.fetch.county._arcgis import ArcGISParcelCAD


NC_DEFAULT_ATTR_MAP: dict[str, list[str]] = {
    "tax_assessed_value":   ["TOTAL_VAL", "TOTAL_VALUE", "ASSESSED_VAL",
                             "TOTALVAL", "ASSESSED"],
    "tax_market_value":     ["MARKET_VAL", "MARKET_VALUE", "TOTAL_MKT"],
    "tax_assessed_year":    ["TAX_YEAR", "ASSESS_YEAR", "YEAR"],
    "lot_size_sqft":        ["GIS_SQFT", "LAND_SQFT", "AREA_SQFT"],
    "lot_size_acres":       ["DEED_ACRES", "GIS_ACRES", "ACRES"],
    "legal_description":    ["LEGAL_DESC", "LEGAL", "PROPERTY_DESC"],
    "owner_name":           ["OWNER", "OWNER_NAME", "OWNER1"],
    "last_sale_price":      ["SALE_PRICE", "TOTSALPRICE", "LAST_SALE"],
    "last_sale_date":       ["SALE_DATE", "TOT_SAL_DATE", "DEED_DATE"],
    "year_built_cad":       ["YEAR_BUILT", "ACT_YR_BLT", "YR_BUILT"],
    "living_area_sqft_cad": ["HEATED_AREA", "TOT_LIVING", "LIVING_AREA"],
    "property_id":          ["PIN", "PARCEL_ID", "REID", "PARCELID"],
}


class NcParcelCAD(ArcGISParcelCAD):
    """ArcGIS parcel CAD with North Carolina defaults (sale price disclosed)."""
    sale_price_disclosed = True
    attr_map = NC_DEFAULT_ATTR_MAP
