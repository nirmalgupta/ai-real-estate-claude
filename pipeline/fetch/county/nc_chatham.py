"""Chatham County, NC — Tax Office.

FIPS 37037. Pittsboro, Siler City, Goldston.

Public endpoint: Chatham publishes a public ArcGIS REST stack on
`gisservices.chathamcountync.gov/opendataagol`. The CAMA-parcel polygon
layer carries owner, FMV/ASV, acreage, legal description and parcel id —
no token, spatial point queries supported:

    gisservices.chathamcountync.gov/.../Cadastral/Chatham_CamaParcels/MapServer/0

Future enhancement: sale price/date and year-built/living-area live in
two geometry-less companion tables (`Chatham_PropertySales`,
`Chatham_PropertyImprovements`), joinable on the (zero-padded)
parcel number. They'd need extra queries beyond the single spatial
lookup the base class performs, so they're deferred for now.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._nc_base import NcParcelCAD


class ChathamNcCAD(NcParcelCAD):
    name = "nc_chatham_cad"
    full_county_fips = "37037"
    county_label = "Chatham County, NC"
    service_url = (
        "https://gisservices.chathamcountync.gov/opendataagol/rest/services/"
        "Cadastral/Chatham_CamaParcels/MapServer/0"
    )

    attr_map = {
        "tax_market_value":   ["jan1_total_FMV"],
        "tax_assessed_value": ["jan1_total_ASV"],
        "tax_assessed_year":  ["parcel_year"],
        "lot_size_acres":     ["gross_current_acres"],
        "legal_description":  ["legal_desc1"],
        "owner_name":         ["current_owners"],
        "property_id":        ["parcel_number", "alternate_parcel_number"],
    }


register("37037", ChathamNcCAD)
