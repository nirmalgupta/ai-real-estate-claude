"""Shared FL-CAD defaults.

Florida is a disclosure state — sale prices are public — so the FL base
sets `sale_price_disclosed = True` and the attr_map includes sale-price
aliases that the TX base intentionally omits.

FL county property appraisers all publish parcel data via ArcGIS REST
(some via county GIS, some via the FGDL clearinghouse). Field naming is
not standardized across counties; each subclass extends or overrides
attr_map as needed.
"""
from __future__ import annotations

from pipeline.fetch.county._arcgis import ArcGISParcelCAD


FL_DEFAULT_ATTR_MAP: dict[str, list[str]] = {
    "tax_assessed_value":   ["JV", "JUST_VALUE", "ASSESSED_VAL", "TOTAL_VAL"],
    "tax_market_value":     ["MARKET_VAL", "MARKET_VALUE", "TOTAL_MKT", "JV"],
    "tax_assessed_year":    ["ASMNT_YR", "TAX_YEAR", "YEAR"],
    "lot_size_sqft":        ["LND_SQFOOT", "LAND_SQFT", "ACT_LND_SQFT"],
    "lot_size_acres":       ["LND_AC", "LAND_ACRES", "ACRES"],
    "legal_description":    ["S_LEGAL", "LEGAL", "LEGAL_DESC"],
    "owner_name":           ["OWN_NAME", "OWNER", "OWNER_NAME"],
    # FL discloses sale price + date — both populated.
    "last_sale_price":      ["SALE_PRC1", "SALE_PRICE", "LAST_SALE_PRC"],
    "last_sale_date":       ["SALE_YR1", "SALE_DATE", "LAST_SALE_DATE"],
    "year_built_cad":       ["EFF_YR_BLT", "ACT_YR_BLT", "YEAR_BUILT"],
    "living_area_sqft_cad": ["TOT_LVG_AR", "LIVING_AREA", "TOTAL_SF"],
    "property_id":          ["PARCEL_ID", "PARCELID", "FOLIO", "STR_BLOCK"],
}


class FlParcelCAD(ArcGISParcelCAD):
    """ArcGIS parcel CAD with Florida defaults (sale price IS disclosed)."""
    sale_price_disclosed = True
    attr_map = FL_DEFAULT_ATTR_MAP
