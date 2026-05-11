"""OpenFEMA NFIP claims by ZIP.

Historical flood-insurance claims paid by the National Flood Insurance
Program — a much better proxy for "does this area actually flood" than
the static NFHL flood zone (which we already pull). A property in zone X
but a ZIP that's logged 200 NFIP claims in 10 years is a yellow flag.

Source: OpenFEMA FimaNfipClaims dataset
    https://www.fema.gov/api/open/v2/FimaNfipClaims

Query: ?$filter=reportedZipCode eq '<zip>' and dateOfLoss ge '<cutoff>'
       &$select=...&$top=1000&$format=json
We $select only the fields we need (date + paid amounts) to keep the
payload small — claims have 70+ fields and ZIPs in flood-prone areas
have hundreds of records.

Returned facts:
    nfip_claims_count_10yr        total claims in ZIP over last 10 yrs
    nfip_claims_total_paid_10yr   sum of building + contents + ICC payouts
    nfip_claims_max_payment       single largest paid claim in that window
    nfip_claims_median_payment    median of per-claim total paid amounts
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from statistics import median

import httpx

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult, Source

OPENFEMA_NFIP = "https://www.fema.gov/api/open/v2/FimaNfipClaims"
LOOKBACK_YEARS = 10
TOP_LIMIT = 1000

# We only need three payment columns; everything else is incidental.
SELECT_FIELDS = (
    "dateOfLoss,amountPaidOnBuildingClaim,amountPaidOnContentsClaim,"
    "amountPaidOnIncreasedCostOfComplianceClaim"
)


def _claim_total(c: dict) -> float:
    """Sum of building + contents + ICC paid amounts for one claim row."""
    total = 0.0
    for k in ("amountPaidOnBuildingClaim", "amountPaidOnContentsClaim",
              "amountPaidOnIncreasedCostOfComplianceClaim"):
        v = c.get(k)
        if isinstance(v, (int, float)):
            total += float(v)
    return total


def _summarize(claims: list[dict]) -> dict:
    """Compute count + max + median + total from a list of claim rows."""
    if not claims:
        return {"count": 0, "total": 0.0, "max": 0.0, "median": 0.0}
    totals = [_claim_total(c) for c in claims]
    return {
        "count": len(claims),
        "total": round(sum(totals), 0),
        "max": round(max(totals), 0),
        "median": round(median(totals), 0),
    }


def _cutoff_iso(years: int, now: datetime | None = None) -> str:
    """Return the YYYY-MM-DD `years` ago in UTC."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=365 * years)
    return cutoff.strftime("%Y-%m-%d")


class FemaNfipSource(Source):
    name = "fema_nfip_claims"

    def fetch(self, address: Address) -> FetchResult:
        zip5 = (address.zip or "")[:5]
        if not zip5 or not zip5.isdigit():
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"No usable ZIP from geocode (got '{address.zip}').",
            )

        cutoff = _cutoff_iso(LOOKBACK_YEARS)
        filt = (
            f"reportedZipCode eq '{zip5}' and dateOfLoss ge '{cutoff}'"
        )
        params = {
            "$filter": filt,
            "$select": SELECT_FIELDS,
            "$top": str(TOP_LIMIT),
            "$format": "json",
        }
        ref = OPENFEMA_NFIP

        try:
            r = httpx.get(OPENFEMA_NFIP, params=params, timeout=45.0)
            r.raise_for_status()
            payload = r.json()
        except (httpx.HTTPError, json.JSONDecodeError) as e:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"OpenFEMA NFIP fetch failed: {e}",
            )

        claims = payload.get("FimaNfipClaims", [])
        summary = _summarize(claims)
        truncated = len(claims) >= TOP_LIMIT

        facts: dict[str, Fact] = {}

        def add(key: str, value, note: str | None = None) -> None:
            facts[key] = Fact(
                value=value, source=self.name, raw_ref=ref, note=note,
            )

        note_window = (
            f"ZIP {zip5}, claims with dateOfLoss ≥ {cutoff}"
            + (" (TRUNCATED at 1000)" if truncated else "")
        )
        add("nfip_claims_count_10yr", summary["count"], note=note_window)
        add("nfip_claims_total_paid_10yr", summary["total"], note=note_window)
        if summary["count"] > 0:
            add("nfip_claims_max_payment", summary["max"], note=note_window)
            add("nfip_claims_median_payment", summary["median"], note=note_window)

        return FetchResult(
            source_name=self.name, address=address, facts=facts,
            raw={"zip": zip5, "cutoff": cutoff, "n_returned": len(claims),
                 "truncated": truncated},
        )
