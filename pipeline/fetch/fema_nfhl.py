"""FEMA National Flood Hazard Layer.

Public ArcGIS REST service. Given a lat/lon, returns the FEMA flood zone
(X / AE / AH / VE etc) for that point. This IS the source of truth —
FEMA's own published map.

API: https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query
Layer 28 = Flood Hazard Zones (the polygons we want).
"""
from __future__ import annotations

import httpx

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult, Source

NFHL_QUERY = (
    "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
)


# Plain-English risk descriptions for the zone codes that actually appear.
ZONE_DESCRIPTIONS = {
    "X": "Minimal flood risk — outside the 0.2% annual chance floodplain",
    "B": "Moderate risk — between the 100-yr and 500-yr floodplain (legacy code, now usually 'X shaded')",
    "C": "Minimal risk (legacy code, now 'X')",
    "AE": "1% annual chance flood (100-yr floodplain) with Base Flood Elevation determined",
    "A": "1% annual chance flood, no Base Flood Elevation determined",
    "AH": "1% annual chance shallow flooding (1-3 ft), usually ponding",
    "AO": "1% annual chance sheet flow flooding on sloping terrain",
    "AR": "Areas with temporarily reduced risk due to a flood control system",
    "A99": "Areas protected from 1% chance flood by a federal flood control system under construction",
    "VE": "Coastal high hazard area with wave action — 1% annual chance flood + waves",
    "V": "Coastal high hazard, no Base Flood Elevation determined",
    "D": "Possible but undetermined flood hazards — area not yet studied",
}


class FemaNFHLSource(Source):
    name = "fema_nfhl"

    def fetch(self, address: Address) -> FetchResult:
        params = {
            "f": "json",
            "geometry": f"{address.lon},{address.lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "FLD_ZONE,ZONE_SUBTY,STATIC_BFE,DEPTH",
            "returnGeometry": "false",
        }
        try:
            r = httpx.get(NFHL_QUERY, params=params, timeout=30.0)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as e:
            return FetchResult(
                source_name=self.name,
                address=address,
                facts={},
                error=f"FEMA NFHL request failed: {e}",
            )

        features = data.get("features", [])
        if not features:
            # No polygon at point => unmapped (treat as Zone X / minimal)
            return FetchResult(
                source_name=self.name,
                address=address,
                facts={
                    "flood_zone": Fact(
                        value="X (unmapped)",
                        source=self.name,
                        raw_ref=NFHL_QUERY,
                        confidence="medium",
                        note="Address falls outside any mapped FEMA flood polygon — typically Zone X.",
                    ),
                    "flood_zone_description": Fact(
                        value=ZONE_DESCRIPTIONS["X"],
                        source=self.name,
                        confidence="medium",
                    ),
                },
                raw=data,
            )

        attrs = features[0]["attributes"]
        zone = attrs.get("FLD_ZONE") or "UNKNOWN"
        subtype = attrs.get("ZONE_SUBTY") or ""
        bfe = attrs.get("STATIC_BFE")
        depth = attrs.get("DEPTH")

        facts = {
            "flood_zone": Fact(
                value=zone,
                source=self.name,
                raw_ref=NFHL_QUERY,
                confidence="high",
                note=subtype or None,
            ),
            "flood_zone_description": Fact(
                value=ZONE_DESCRIPTIONS.get(zone, "Unrecognized FEMA zone code"),
                source=self.name,
                confidence="high",
            ),
        }
        if bfe is not None and bfe != -9999:
            facts["base_flood_elevation_ft"] = Fact(value=bfe, source=self.name)
        if depth is not None and depth != -9999:
            facts["flood_depth_ft"] = Fact(value=depth, source=self.name)

        return FetchResult(source_name=self.name, address=address, facts=facts, raw=data)
