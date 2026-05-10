"""USGS earthquake-hazard fetcher.

Returns peak ground acceleration (PGA) at the property lat/lon with
2% probability of exceedance in 50 years — the standard "design-level"
seismic hazard metric used in building codes (ASCE 7).

Data source: USGS National Seismic Hazard Model (NSHM) hazard service.
The service returns a hazard curve mapping annual exceedance frequency
to ground motion. We interpolate the curve at the 2%-in-50yr target
frequency:

    target = -ln(1 - 0.02) / 50  ≈  0.000404 / yr

The fetcher is meaningful for the entire conterminous US — even low-
seismicity regions get a value (just a small one). That is the point of
the metric for the comparison case.
"""
from __future__ import annotations

import math
from typing import Any

import httpx

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult, Source

# Modern USGS NSHM web service. The URL accepts both COUS (conterminous
# US) and AK, HI editions. We default to COUS; outside that region the
# service returns an error envelope and the fetcher reports cleanly.
NSHM_BASE = "https://earthquake.usgs.gov/nshmp-haz-ws/hazard"
EDITION = "E2014R1"          # 2014 NSHM, revision 1 — the stable service edition
REGION = "COUS"              # Conterminous US
IMT = "PGA"                  # Peak Ground Acceleration
VS30 = "760"                 # Site class B/C boundary (ASCE 7 reference)

EXCEEDANCE_PROB = 0.02
RETURN_PERIOD_YEARS = 50.0
TARGET_AFE = -math.log(1 - EXCEEDANCE_PROB) / RETURN_PERIOD_YEARS  # ≈ 4.04e-4


def _interp_loglog(curve: list[tuple[float, float]], target_y: float) -> float | None:
    """Log-log interpolate a (x=ground motion, y=annual freq) curve.

    USGS hazard curves are conventionally plotted log-log; linear
    interpolation in log space matches how the curves are defined.
    Returns None if the target lies outside the curve's range.
    """
    if not curve:
        return None
    sorted_pts = sorted(curve, key=lambda p: p[1], reverse=True)  # high freq first
    for i in range(len(sorted_pts) - 1):
        (x1, y1), (x2, y2) = sorted_pts[i], sorted_pts[i + 1]
        if y2 <= target_y <= y1 and x1 > 0 and x2 > 0 and y1 > 0 and y2 > 0:
            log_x = (
                math.log(x1)
                + (math.log(target_y) - math.log(y1))
                * (math.log(x2) - math.log(x1))
                / (math.log(y2) - math.log(y1))
            )
            return math.exp(log_x)
    return None


def _parse_curve(payload: Any) -> list[tuple[float, float]]:
    """Pull the (PGA, annual_freq) pairs out of the NSHM response.

    USGS returns a dict with `response[].data[].xvalues` (PGA in g) and
    `yvalues` (annual exceedance frequency). We walk defensively because
    the service has shipped multiple envelope shapes.
    """
    if not isinstance(payload, dict):
        return []
    responses = payload.get("response")
    if not isinstance(responses, list):
        return []
    for resp in responses:
        metadata = resp.get("metadata") or {}
        if str(metadata.get("imt", "")).upper() != "PGA":
            continue
        data_blocks = resp.get("data")
        if not isinstance(data_blocks, list):
            continue
        for d in data_blocks:
            if d.get("component") not in (None, "Total", "TOTAL"):
                continue
            xs = d.get("xvalues") or metadata.get("xvalues")
            ys = d.get("yvalues")
            if not (isinstance(xs, list) and isinstance(ys, list)):
                continue
            return [(float(x), float(y)) for x, y in zip(xs, ys) if x and y]
    return []


class UsgsEqSource(Source):
    name = "usgs_eq"

    def fetch(self, address: Address) -> FetchResult:
        url = f"{NSHM_BASE}/{EDITION}/{REGION}/{address.lon}/{address.lat}/{IMT}/{VS30}"
        try:
            r = httpx.get(url, timeout=30.0)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as e:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"USGS NSHM request failed: {e}",
            )

        if not isinstance(data, dict) or data.get("status") == "error":
            msg = (data.get("message") if isinstance(data, dict) else None) or "unknown"
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"USGS NSHM returned error: {msg}",
            )

        curve = _parse_curve(data)
        pga = _interp_loglog(curve, TARGET_AFE) if curve else None

        if pga is None:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error="USGS NSHM returned no usable hazard curve at this point.",
            )

        facts = {
            "seismic_pga_2pct_50yr": Fact(
                value=round(pga, 4),
                source=self.name,
                raw_ref=url,
                note=(
                    "Peak ground acceleration (g) with 2% probability of "
                    "exceedance in 50 years (ASCE 7 design-basis level). "
                    "Site class B/C, vs30=760 m/s."
                ),
            ),
        }
        return FetchResult(source_name=self.name, address=address, facts=facts, raw=data)
