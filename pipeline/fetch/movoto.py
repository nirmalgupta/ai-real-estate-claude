"""Movoto.com listing scraper (manual-URL only).

Movoto's address search is JS-rendered and never returned a usable
listing URL from our HTTP client. Redfin (`pipeline.fetch.redfin`) now
covers the same fields with a more reliable JSON-LD-backed scrape, so
the auto-discovery path has been retired (issue #39).

Movoto still runs when the user passes `--movoto-url <url>` explicitly
— useful when Redfin doesn't carry the listing but Movoto does. With
no URL the fetcher returns a clean skip, not an error.
"""
from __future__ import annotations

import re
from pathlib import Path

import httpx

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult, Source

DEFAULT_RAW_DIR = Path(__file__).resolve().parent.parent.parent / "wiki" / "raw"

# Realistic Chrome-on-macOS UA. Avoids the "python-httpx/X.Y" default that
# everyone blocks.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.5 Safari/605.1.15"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    # No Brotli — httpx needs a separate brotli package to decompress 'br'.
    # gzip/deflate cover ~all CDN responses fine.
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


def _extract_first_match(pattern: str, html: str) -> str | None:
    m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None


def _to_int(s: str | None) -> int | None:
    if s is None:
        return None
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None


def _to_float(s: str | None) -> float | None:
    if s is None:
        return None
    cleaned = re.sub(r"[^\d.]", "", s)
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return None


class MovotoSource(Source):
    name = "movoto"

    def __init__(self, raw_dir: Path = DEFAULT_RAW_DIR, listing_url: str | None = None):
        self.raw_dir = raw_dir
        self.listing_url_override = listing_url

    def fetch(self, address: Address) -> FetchResult:
        listing_url = self.listing_url_override
        if listing_url is None:
            return FetchResult(
                source_name=self.name,
                address=address,
                facts={},
                error=(
                    "Movoto skipped — no --movoto-url provided. Redfin is "
                    "the default listing source; pass --movoto-url <url> "
                    "only when Movoto carries a listing Redfin doesn't."
                ),
            )

        try:
            r = httpx.get(listing_url, headers=BROWSER_HEADERS, timeout=30.0,
                          follow_redirects=True)
            if r.status_code in (401, 403, 429):
                return FetchResult(
                    source_name=self.name,
                    address=address,
                    facts={},
                    error=f"Movoto blocked request ({r.status_code}). "
                          "Try again later or upgrade to playwright-stealth.",
                )
            r.raise_for_status()
        except httpx.HTTPError as e:
            return FetchResult(
                source_name=self.name,
                address=address,
                facts={},
                error=f"Movoto fetch failed: {e}",
            )

        html = r.text
        # Save raw HTML for downstream LLM extraction
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = self.raw_dir / f"{address.slug}.movoto.html"
        raw_path.write_text(html)

        # Heuristic extraction of high-confidence fields. Anything more
        # subjective is left for the LLM layer reading the raw HTML.
        list_price = _to_int(
            _extract_first_match(r'"price"\s*:\s*"?\$?([\d,]+)"?', html)
            or _extract_first_match(r'\$([\d,]{6,})\s*(?:</|<span)', html)
        )
        beds = _to_int(_extract_first_match(r'(\d+)\s*(?:bed|bd)\b', html))
        baths_total = _to_float(_extract_first_match(r'(\d+(?:\.\d+)?)\s*(?:bath|ba)\b', html))
        sqft = _to_int(_extract_first_match(r'([\d,]{3,7})\s*sq(?:uare)?\s*ft', html))
        year_built = _to_int(_extract_first_match(r'[Bb]uilt\s+in\s+(\d{4})', html))

        # Lot size: residential lots are almost always <10 acres. The naive
        # `([\d.]+) acres?` regex hits "1,800 acres" in nature-preserve
        # boilerplate. Restrict to a leading 0 (e.g. 0.32) or a single-digit
        # whole/decimal (e.g. 5.5). Anything else is left for the LLM layer.
        lot_size_acres = _to_float(_extract_first_match(
            r'\b(0\.\d+|[1-9]\.\d+|[1-9])\s*acres?\b', html
        ))

        facts: dict[str, Fact] = {
            "movoto_url": Fact(value=listing_url, source=self.name, raw_ref=listing_url),
            "movoto_raw_html": Fact(value=str(raw_path), source=self.name, raw_ref=listing_url),
        }
        for k, v in [
            ("list_price", list_price),
            ("beds", beds),
            ("baths_total", baths_total),
            ("sqft", sqft),
            ("year_built", year_built),
            ("lot_size_acres", lot_size_acres),
        ]:
            if v is not None:
                facts[k] = Fact(
                    value=v, source=self.name, raw_ref=listing_url,
                    confidence="medium",
                    note="regex-extracted; verify against LLM extraction of raw HTML",
                )

        return FetchResult(
            source_name=self.name,
            address=address,
            facts=facts,
            raw={"url": listing_url, "html_path": str(raw_path), "html_bytes": len(html)},
        )

