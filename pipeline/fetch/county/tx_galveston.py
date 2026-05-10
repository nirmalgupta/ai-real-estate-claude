"""Galveston County, TX — GCAD.

FIPS 48167. Galveston, Texas City, League City, Friendswood, Dickinson.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


class GalvestonTxCAD(TxParcelCAD):
    name = "tx_galveston_cad"
    full_county_fips = "48167"
    county_label = "Galveston County, TX"
    service_url = (
        "https://services2.arcgis.com/uGo7PKALPg93ZiO2/arcgis/rest/services/"
        "Galveston_County_Appraisal_District_Parcels_and_Lot_Lines/"
        "FeatureServer/2"
    )

    attr_map = {
        "tax_assessed_value":     ["VAL_TOT"],
        "tax_market_value":       ["VAL_TOT"],
        "legal_description":      ["LEGAL"],
        "situs_address":          ["SITUS", "ADDRESS"],
    }


register("48167", GalvestonTxCAD)
