"""Durham County, NC — Assessor.

FIPS 37063. Durham proper, parts of RTP.

Public endpoint: served via the NC OneMap statewide parcel service
(layer 1 = parcel polygons), which carries Durham with standardized
fields — no token, spatial point queries supported:

    https://services.nconemap.gov/secure/rest/services/NC1Map_Parcels/FeatureServer/1

Coverage note: for Durham this statewide layer populates assessed value,
owner, lot size and parcel id, but NOT year built (`structyear` is 0),
living area, legal description (empty), or sale price/date — those
columns aren't filled by Durham's submission. Durham County's own CAMA
service is not published at a stable public REST path
(`gisweb/gis/maps.durhamnc.gov`, `spatialdata.dconc.gov` all 404 on the
standard ArcGIS path), so this is the best public source today.
"""
from __future__ import annotations

from pipeline.fetch.county import register
from pipeline.fetch.county._nc_base import NcParcelCAD


class DurhamNcCAD(NcParcelCAD):
    name = "nc_durham_cad"
    full_county_fips = "37063"
    county_label = "Durham County, NC"
    service_url = (
        "https://services.nconemap.gov/secure/rest/services/"
        "NC1Map_Parcels/FeatureServer/1"
    )

    attr_map = {
        "tax_assessed_value": ["parval"],
        "lot_size_sqft":      ["Shape__Area", "Shape_Area"],
        "lot_size_acres":     ["gisacres"],
        "owner_name":         ["ownname", "ownname2"],
        "property_id":        ["parno", "altparno"],
    }


register("37063", DurhamNcCAD)
