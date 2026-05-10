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

        add("list_price", _to_int(offers.get("price")))
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

        return FetchResult(
            source_name=self.name, address=address, facts=facts,
            raw={"raw_path": str(raw_path), "listing_url": listing_url},
        )
