"""Montgomery County, TX — MCAD.

FIPS 48339. The Woodlands, Conroe, Spring (north), Magnolia.

Note: the public Tax_Parcel_view feature service publishes parcels
with owner + situs + legal + year built, but NOT the appraisal values
(those live on MCAD's HTML property-search portal, which is not a
JSON API). The assessed/market value Facts will simply be missing.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._tx_base import TxParcelCAD


class MontgomeryTxCAD(TxParcelCAD):
    name = "tx_montgomery_cad"
    full_county_fips = "48339"
    county_label = "Montgomery County, TX"
    service_url = (
        "https://services1.arcgis.com/PRoAPGnMSUqvTrzq/arcgis/rest/services/"
        "Tax_Parcel_view/FeatureServer/0"
    )

    attr_map = {
        "tax_assessed_year":      ["pYear"],
        "legal_description":      ["legalDescription"],
        "owner_name":             ["ownerName"],
        "year_built_cad":         ["imprvActualYearBuilt"],
        "property_id":            ["PIN"],
        "situs_address":          ["situs"],
    }


register("48339", MontgomeryTxCAD)
