"""Shared TX-CAD defaults.

All Texas county adapters share two things:
1. Sale prices are not disclosed (TX is a non-disclosure state).
2. The standard set of attribute aliases that TX CADs typically use
   for assessed value, lot size, owner, etc.

Subclasses set `service_url` (and override `attr_map` if their portal
ships unusual key names).
"""
from __future__ import annotations

from pipeline.fetch.county._arcgis import ArcGISParcelCAD


# Common TX CAD attribute aliases. Counties using TylerTech / TrueAutomation
# / Harris Govern iAS export overlapping field names. This map is the
# "typical" set; individual counties extend or override.
TX_DEFAULT_ATTR_MAP: dict[str, list[str]] = {
    "tax_assessed_value":   ["TOTAL_APPRAISED_VAL", "TOTAL_APPRAISED_VALUE",
                             "ASSESSED", "APPRAISED_VAL", "TOTAL_VAL", "TOTAL_VALUE"],
    "tax_market_value":     ["TOTAL_MARKET_VALUE", "MARKET_VAL", "MARKET_VALUE"],
    "tax_assessed_year":    ["APPRAISAL_YEAR", "TAX_YEAR", "YEAR"],
    "lot_size_sqft":        ["LAND_SQFT", "GIS_SQFT", "LANDSQFT"],
    "lot_size_acres":       ["LAND_ACRES", "GIS_ACRES", "ACRES", "ACRE"],
    "legal_description":    ["LEGAL_DESC", "LEGAL", "LEGAL_LINE_1"],
    "owner_name":           ["OWNER_NAME", "OWNER", "OWNER1"],
    "last_deed_date":       ["DEED_DATE", "TRANSFER_DATE", "SALE_DATE"],
    "year_built_cad":       ["YEAR_BUILT", "ACTUAL_YEAR_BUILT", "YR_BUILT"],
    "living_area_sqft_cad": ["LIVING_AREA", "LIVING_SQFT", "TOTAL_SF",
                             "TOTAL_LIVING_AREA", "BLDG_SF"],
    "property_id":          ["PROP_ID", "PROPERTY_ID", "PIN", "ACCOUNT_NUM",
                             "ACCT", "GEO_ID"],
}


class TxParcelCAD(ArcGISParcelCAD):
    """ArcGIS parcel CAD with Texas-state defaults."""
    sale_price_disclosed = False
    attr_map = TX_DEFAULT_ATTR_MAP
