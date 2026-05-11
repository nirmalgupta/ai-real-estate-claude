"""Redfin per-property HTML fetcher.

Companion to MovotoSource — Redfin has different AVM logic, different
price-history view, and (sometimes) a richer listing description, so
it's worth pulling both for any property where both have a listing.

Strategy mirrors MovotoSource:
1. Resolve a listing URL (caller passes `--redfin-url`, or we try to
   find one from a recent Redfin search).
2. Fetch the HTML detail page (200 OK to plain HTTP with browser UA).
3. Save raw HTML to `wiki/raw/<slug>.redfin.html` for downstream
   LLM extraction.
4. Pull high-confidence structured data from the schema.org
   `RealEstateListing` JSON-LD block embedded in the page.

What we extract via JSON-LD:
    list price, beds, baths, sqft, year_built, redfin URL, image, lat/lon,
    description, datePosted, mainEntity.accommodationCategory.

What we leave for the LLM layer (no clean structured data — sits in
React-server-rendered DOM that drifts often): Redfin Estimate, price
history table, tax history, school ratings, days on Redfin.

Note: Redfin's per-property JSON API endpoints (`stingray/api/home/
details/*`) are CloudFront-blocked. The HTML page is the only public
plain-HTTP path.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import httpx

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult, Source

DEFAULT_RAW_DIR = Path(__file__).resolve().parent.parent.parent / "wiki" / "raw"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}

# Greedy across newlines because the JSON-LD blob is one minified line
# but is wrapped in a <script> tag that may span lines on some pages.
LD_JSON_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>',
    re.DOTALL,
)


def _find_listing_block(html: str) -> dict | None:
    """Return the parsed RealEstateListing ld+json block, or None."""
    for body in LD_JSON_RE.findall(html):
        try:
            obj = json.loads(body)
        except json.JSONDecodeError:
            continue
        t = obj.get("@type")
        if isinstance(t, list):
            if "RealEstateListing" in t:
                return obj
        elif t == "RealEstateListing":
            return obj
    return None


def _to_int(v) -> int | None:
    if v is None:
        return None
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return None


def _to_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


# One row of Redfin's sale-history table. The HTML structure is:
#   <div class="BasicTable__row ...">
#     <div class="BasicTable__col date">Apr 30, 2026</div>
#     <div class="BasicTable__col event">Listed</div>
#     <div class="BasicTable__col price">$1,049,000<p class="subtext">$<!-- -->262<!-- -->/sq ft</p></div>
#   </div>
_HISTORY_ROW_RE = re.compile(
    r'<div class="BasicTable__col date">([^<]+)</div>'
    r'<div class="BasicTable__col event">([^<]+)</div>'
    r'<div class="BasicTable__col price">(.*?)</div>',
    re.DOTALL,
)
_PRICE_RE = re.compile(r'\$([\d,]+)')
_PPSQFT_RE = re.compile(r'\$<!--\s*-->(\d+)<!--\s*-->/sq ft')


def _parse_price_history(html: str) -> list[dict]:
    """Pull the Sale History table out of Redfin's per-property HTML.

    Each entry: {date, event, price (int or None), price_per_sqft}.
    TX-non-disclosure rows have price='*' in the HTML — we surface them
    with price=None and a note so the caller knows the row exists.
    """
    events: list[dict] = []
    for date_str, event, price_blob in _HISTORY_ROW_RE.findall(html):
        # Skip "—" or pure dashes which appear on Contingent/Pending rows.
        price_m = _PRICE_RE.search(price_blob)
        ppsqft_m = _PPSQFT_RE.search(price_blob)
        events.append({
            "date": date_str.strip(),
            "event": event.strip(),
            "price": int(price_m.group(1).replace(",", "")) if price_m else None,
            "price_per_sqft": int(ppsqft_m.group(1)) if ppsqft_m else None,
            "non_disclosure": "*" in price_blob and price_m is None and event.strip() == "Sold",
        })
    return events


def _is_on_market(block: dict, history: list[dict]) -> bool:
    """Decide whether a Redfin schema.org block represents an active listing.

    Redfin reuses the `offers.price` field for off-market homes — but the
    value is the Redfin Estimate (AVM), not a seller's ask. Surfacing it
    as `list_price` misleads downstream consumers (cash-flow, break-even,
    LLM-drafted snapshot). We need to tell the cases apart.

    Signal priority:
      1. `offers.availability` is authoritative when present.
      2. Otherwise, fall back to the most recent priced event in the
         sale history table — `Listed` means the home is on-market,
         anything else (Sold, Listing Removed, Pending) means off-market.
      3. If neither signal exists, treat as on-market (legacy behavior
         for pages that lack both fields).
    """
    offers = block.get("offers") or {}
    avail = offers.get("availability")
    if avail:
        avail_str = str(avail).lower()
        if "instock" in avail_str:
            return True
        return False
    if history:
        latest = history[0]
        return latest.get("event", "").lower() == "listed"
    return True


def _implied_list_appreciation(history: list[dict]) -> dict | None:
    """If we have ≥2 list events with prices, compute implied annualized
    appreciation from prior list → most recent list. Useful sanity check
    against the configurable forward-appreciation rate.
    """
    list_events = [
        e for e in history
        if e["event"].lower() == "listed" and e["price"] is not None
    ]
    if len(list_events) < 2:
        return None
    try:
        # History is ordered newest-first in the Redfin HTML.
        new_e, old_e = list_events[0], list_events[-1]
        new_dt = datetime.strptime(new_e["date"], "%b %d, %Y")
        old_dt = datetime.strptime(old_e["date"], "%b %d, %Y")
    except ValueError:
        return None
    years = (new_dt - old_dt).days / 365.25
    if years <= 0 or old_e["price"] <= 0:
        return None
    ratio = new_e["price"] / old_e["price"]
    annual = ratio ** (1 / years) - 1
    return {
        "from_date": old_e["date"],
        "from_price": old_e["price"],
        "to_date": new_e["date"],
        "to_price": new_e["price"],
        "years_between": round(years, 2),
        "implied_annual_rate": round(annual, 4),
    }


class RedfinSource(Source):
    name = "redfin"

    def __init__(self, raw_dir: Path = DEFAULT_RAW_DIR, listing_url: str | None = None):
        self.raw_dir = raw_dir
        self.listing_url_override = listing_url

    def fetch(self, address: Address) -> FetchResult:
        listing_url = self.listing_url_override
        if listing_url is None:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=(
                    "No Redfin listing URL provided. Run "
                    "`python3 -m pipeline.search` to find candidates and "
                    "pass the URL as --redfin-url <listing-url>."
                ),
            )

        try:
            r = httpx.get(listing_url, headers=BROWSER_HEADERS, timeout=30.0,
                          follow_redirects=True)
            if r.status_code in (401, 403, 429):
                return FetchResult(
                    source_name=self.name, address=address, facts={},
                    error=f"Redfin blocked request ({r.status_code}). "
                          "Try again later or use --movoto-url instead.",
                )
            r.raise_for_status()
        except httpx.HTTPError as e:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"Redfin fetch failed: {e}",
            )

        html = r.text
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = self.raw_dir / f"{address.slug}.redfin.html"
        raw_path.write_text(html)

        block = _find_listing_block(html)
        if block is None:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error="Redfin page fetched but no RealEstateListing JSON-LD "
                      "block found. Raw HTML saved for LLM extraction.",
                raw={"raw_path": str(raw_path)},
            )

        ref = listing_url
        facts: dict[str, Fact] = {}

        def add(key: str, value, note: str | None = None) -> None:
            if value is None or value == "":
                return
            facts[key] = Fact(
                value=value, source=self.name, raw_ref=ref, note=note,
            )

        offers = block.get("offers") or {}
        main = block.get("mainEntity") or {}
        floor = (main.get("floorSize") or {}) if isinstance(main, dict) else {}

        history = _parse_price_history(html)
        on_market = _is_on_market(block, history)
        price = _to_int(offers.get("price"))
        if on_market:
            add("list_price", price)
        else:
            add("redfin_estimate", price,
                note="Redfin AVM for off-market home (offers.price on a "
                     "non-listed property is the Redfin Estimate, not a "
                     "seller's ask)")
        add("listing_url", block.get("url"))
        add("listing_description", block.get("description"))
        add("listing_date_posted", block.get("datePosted"))
        add("listing_last_reviewed", block.get("lastReviewed"))
        add("beds", _to_int(main.get("numberOfBedrooms")))
        add("baths_total", _to_float(main.get("numberOfBathroomsTotal")))
        add("year_built_listing", _to_int(main.get("yearBuilt")))
        add("living_area_sqft_listing", _to_int(floor.get("value")),
            note="Floor area from Redfin schema.org block (FTK = sq ft)")
        add("property_type_redfin", main.get("accommodationCategory"))

        # Image count is a useful "professional listing?" signal.
        images = block.get("image") if isinstance(block.get("image"), list) else None
        if images:
            add("photo_count", len(images))

        # Sale history table — clean HTML, scrapable regardless of state.
        if history:
            add("redfin_price_history", history,
                note=f"{len(history)} historical event(s); '*' price rows "
                     "are sales hidden by state non-disclosure laws")
            implied = _implied_list_appreciation(history)
            if implied is not None:
                add("redfin_implied_list_appreciation", implied,
                    note=(
                        f"Annualized appreciation between prior list "
                        f"({implied['from_date']}: ${implied['from_price']:,}) "
                        f"and current list "
                        f"({implied['to_date']}: ${implied['to_price']:,}). "
                        "Useful sanity-check for forward-projection assumptions."
                    ))

        return FetchResult(
            source_name=self.name, address=address, facts=facts,
            raw={"raw_path": str(raw_path), "listing_url": listing_url},
        )
