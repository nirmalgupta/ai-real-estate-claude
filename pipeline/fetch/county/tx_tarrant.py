"""Tarrant County, TX — TAD (tad.org).

FIPS 48439. Fort Worth, Arlington, Grand Prairie (west), Mansfield.

Public endpoint: the City of Fort Worth hosts a public ArcGIS Online
view of the full TAD appraisal roll (743k+ parcels, all jurisdictions in
the county) with owner, appraised/market value, land area, legal
description, year built and living area — no token, spatial point
queries supported:

    services5.arcgis.com/3ddLCBXe1bRt7mzj/.../Parcels_Public_Vview/FeatureServer/0

(The service name is misspelled "Vview" upstream — kept verbatim.) TAD's
own portal and the county `mapit.tarrantcounty.com` service only expose
county-government-owned parcels, which is why earlier probes came up
short; this CFW-hosted view is the full roll.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


class TarrantTxCAD(TxParcelCAD):
    name = "tx_tarrant_cad"
    full_county_fips = "48439"
    county_label = "Tarrant County, TX"
    service_url = (
        "https://services5.arcgis.com/3ddLCBXe1bRt7mzj/arcgis/rest/services/"
        "Parcels_Public_Vview/FeatureServer/0"
    )

    attr_map = {
        "tax_assessed_value":   ["APPRAISED_VALUE", "TAXABLE_VALUE"],
        "tax_market_value":     ["MARKET_VALUE"],
        "tax_assessed_year":    ["TAX_YEAR"],
        "lot_size_sqft":        ["LAND_SQFT"],
        "lot_size_acres":       ["LAND_ACRE"],
        "legal_description":    ["PARCEL_LEGAL_DESCRIPTION"],
        "owner_name":           ["OWNER_NAME"],
        "last_deed_date":       ["DEED_DATE"],
        "year_built_cad":       ["YR_BUILT"],
        "living_area_sqft_cad": ["LIVING_AREA"],
        "property_id":          ["ACCOUNT", "TAXPIN", "PIDN"],
    }


register("48439", TarrantTxCAD)
