"""Redfin sold-comp finder.

Replaces the LLM-WebSearch comp section with deterministic data:
queries Redfin's gis-csv endpoint with `status=SOLD` in a buffer around
the subject property, then ranks by similarity (size + bedroom + recency
+ distance).

Behavior:
  - Tries a strict filter first: 1 mi radius, ±30% sqft, ±1 bed, same
    property type, last 12 mo. If <3 matches survive, retries with a
    wider radius and looser size band, then notes which tier produced
    the comps.
  - TX / other non-disclosure markets often have blank PRICE on sold
    rows — those are dropped, since a comp with no sold price isn't
    useful. The fetcher returns whatever priced comps survived plus the
    filter tier label.
  - On total failure (0 comps even after relaxed retry) the fact is
    omitted; the SKILL.md drafting falls back to its old LLM-WebSearch
    path.

Output fact `comparable_sales` is a list of dicts:
    [{ address, sold_date, sold_price, price_per_sqft, beds, baths,
       sqft, lot_sqft, year_built, distance_miles, url }, ...]
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult, Source
from pipeline.search.redfin import Listing, STATUS_SOLD, search_redfin

LOOKBACK_MONTHS = 12
DEFAULT_N = 6


def _haversine_miles(lat1: float, lon1: float,
                     lat2: float, lon2: float) -> float:
    r = 3958.7613
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _parse_sold_date(s: str | None) -> datetime | None:
    if not s:
        return None
    # Redfin emits sold dates in a few different formats across markets
    for fmt in ("%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _passes_filter(L: Listing, *, subject_lat: float, subject_lon: float,
                   subject_sqft: int | None, subject_beds: int | None,
                   subject_type: str | None,
                   radius_miles: float, sqft_band: float, bed_band: int,
                   cutoff: datetime) -> bool:
    if L.price is None or L.price <= 0:
        return False
    if L.lat is None or L.lon is None:
        return False
    if _haversine_miles(subject_lat, subject_lon, L.lat, L.lon) > radius_miles:
        return False

    sold = _parse_sold_date(L.sold_date)
    if sold is None or sold < cutoff:
        return False

    if subject_sqft and L.sqft:
        lo, hi = subject_sqft * (1 - sqft_band), subject_sqft * (1 + sqft_band)
        if not (lo <= L.sqft <= hi):
            return False

    if subject_beds and L.beds is not None:
        if abs(L.beds - subject_beds) > bed_band:
            return False

    if subject_type and L.property_type:
        # Loose equality on the prefix (e.g. "Single Family Residential" vs
        # "Single Family Detached")
        if subject_type.split()[0].lower() != L.property_type.split()[0].lower():
            return False

    return True


def _similarity_score(L: Listing, subject_sqft: int | None,
                      subject_lat: float, subject_lon: float,
                      cutoff: datetime) -> float:
    """Composite ranking score — lower is better.

    Penalize by relative sqft delta, distance, and age. Comps without a
    sqft or sold_date sink to the bottom of the ranking but still appear.
    """
    sqft_pen = 0.0
    if subject_sqft and L.sqft:
        sqft_pen = abs(L.sqft - subject_sqft) / max(subject_sqft, 1)
    dist = 0.0
    if L.lat is not None and L.lon is not None:
        dist = _haversine_miles(subject_lat, subject_lon, L.lat, L.lon)
    age_days = 0.0
    sold = _parse_sold_date(L.sold_date)
    if sold:
        age_days = (datetime.now(timezone.utc) - sold).days
    # Weights: sqft delta 1.0, distance 0.5/mi, age 0.001/day
    return sqft_pen + dist * 0.5 + age_days * 0.001


def _to_comp_dict(L: Listing, subject_lat: float, subject_lon: float) -> dict:
    dist = (
        round(_haversine_miles(subject_lat, subject_lon, L.lat, L.lon), 2)
        if L.lat is not None and L.lon is not None else None
    )
    return {
        "address": L.display_addr,
        "sold_date": L.sold_date,
        "sold_price": L.price,
        "price_per_sqft": L.price_per_sqft,
        "beds": L.beds,
        "baths": L.baths,
        "sqft": L.sqft,
        "lot_sqft": L.lot_sqft,
        "year_built": L.year_built,
        "distance_miles": dist,
        "url": L.url,
    }


class RedfinCompsSource(Source):
    name = "redfin_comps"

    def __init__(self, subject_sqft: int | None = None,
                 subject_beds: int | None = None,
                 subject_type: str | None = None,
                 n: int = DEFAULT_N):
        self.subject_sqft = subject_sqft
        self.subject_beds = subject_beds
        self.subject_type = subject_type
        self.n = n

    def fetch(self, address: Address) -> FetchResult:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30 * LOOKBACK_MONTHS)

        tiers = [
            ("strict", {"radius_miles": 1.0, "sqft_band": 0.30, "bed_band": 1}),
            ("relaxed", {"radius_miles": 2.5, "sqft_band": 0.50, "bed_band": 2}),
        ]
        comps: list[Listing] = []
        used_tier = None
        all_query_urls: list[str] = []

        for tier_name, params in tiers:
            try:
                rows, qurl = search_redfin(
                    center_lat=address.lat,
                    center_lon=address.lon,
                    radius_miles=params["radius_miles"],
                    max_results=350,
                    status=STATUS_SOLD,
                )
            except Exception as e:  # network/parsing failure
                return FetchResult(
                    source_name=self.name, address=address, facts={},
                    error=f"Redfin sold query failed: {e}",
                )
            all_query_urls.append(qurl)
            comps = [
                L for L in rows
                if _passes_filter(
                    L, subject_lat=address.lat, subject_lon=address.lon,
                    subject_sqft=self.subject_sqft,
                    subject_beds=self.subject_beds,
                    subject_type=self.subject_type,
                    radius_miles=params["radius_miles"],
                    sqft_band=params["sqft_band"],
                    bed_band=params["bed_band"],
                    cutoff=cutoff,
                )
            ]
            if len(comps) >= 3:
                used_tier = tier_name
                break

        if not comps:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error="No qualifying Redfin sold comps in 12mo window — "
                      "likely non-disclosure state with blank PRICE or rural "
                      "area with thin coverage.",
            )

        comps.sort(
            key=lambda L: _similarity_score(
                L, self.subject_sqft, address.lat, address.lon, cutoff,
            )
        )
        chosen = comps[: self.n]
        comp_dicts = [_to_comp_dict(L, address.lat, address.lon) for L in chosen]

        ref = all_query_urls[-1]
        facts = {
            "comparable_sales": Fact(
                value=comp_dicts, source=self.name, raw_ref=ref,
                note=(
                    f"{len(chosen)} Redfin sold comp(s), {used_tier or 'relaxed'} "
                    f"filter, last {LOOKBACK_MONTHS}mo. Ranked by sqft similarity "
                    "+ distance + recency."
                ),
            ),
            "comparable_sales_filter_tier": Fact(
                value=used_tier or "relaxed", source=self.name, raw_ref=ref,
            ),
        }

        return FetchResult(
            source_name=self.name, address=address, facts=facts,
            raw={"n_comps": len(chosen), "tier": used_tier,
                 "query_urls": all_query_urls},
        )
