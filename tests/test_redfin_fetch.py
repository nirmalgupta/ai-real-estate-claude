"""Pure-logic tests for the Redfin per-property fetcher (no network)."""
import json
import unittest

from pipeline.fetch.redfin import (
    _find_listing_block,
    _implied_list_appreciation,
    _parse_price_history,
    _to_float,
    _to_int,
)


SAMPLE_BLOCK = {
    "@context": "https://schema.org",
    "@type": ["Product", "RealEstateListing"],
    "name": "5646 Highflyer Hills Trl",
    "description": "Discover the perfect blend...",
    "url": "https://www.redfin.com/TX/Frisco/5646-Highflyer-Hills-Trl-75036/home/104485204",
    "datePosted": "2026-04-30T20:09:49.247Z",
    "offers": {
        "@type": "Offer",
        "price": "1049000",
        "priceCurrency": "USD",
    },
    "mainEntity": {
        "@type": "SingleFamilyResidence",
        "numberOfBedrooms": "5",
        "numberOfBathroomsTotal": "5",
        "yearBuilt": "2016",
        "accommodationCategory": "Single Family Residential",
        "floorSize": {"value": "4005", "unitText": "FTK"},
    },
    "image": [{"url": f"x{i}"} for i in range(40)],
}


def _wrap_html(blocks: list[dict]) -> str:
    parts = [
        '<html><head>',
        '<script type="application/ld+json">{"@context":"http://schema.org","@type":"Organization","name":"Redfin"}</script>',
    ]
    for b in blocks:
        parts.append(f'<script type="application/ld+json">{json.dumps(b)}</script>')
    parts.append('</head><body></body></html>')
    return "".join(parts)


class TestFindBlock(unittest.TestCase):
    def test_finds_real_estate_listing(self):
        html = _wrap_html([SAMPLE_BLOCK])
        block = _find_listing_block(html)
        self.assertIsNotNone(block)
        self.assertEqual(block["mainEntity"]["yearBuilt"], "2016")

    def test_handles_type_as_string(self):
        b = dict(SAMPLE_BLOCK)
        b["@type"] = "RealEstateListing"
        block = _find_listing_block(_wrap_html([b]))
        self.assertIsNotNone(block)

    def test_skips_unrelated_ld_json(self):
        html = _wrap_html([])  # only the Organization block
        self.assertIsNone(_find_listing_block(html))

    def test_returns_none_when_no_ld_json(self):
        self.assertIsNone(_find_listing_block("<html></html>"))


class TestCoercers(unittest.TestCase):
    def test_int(self):
        self.assertEqual(_to_int("1,049,000"), 1049000)
        self.assertEqual(_to_int("5"), 5)
        self.assertIsNone(_to_int(""))
        self.assertIsNone(_to_int(None))
        self.assertIsNone(_to_int("abc"))

    def test_float(self):
        self.assertEqual(_to_float("5.0"), 5.0)
        self.assertEqual(_to_float("4,005"), 4005.0)
        self.assertIsNone(_to_float(None))


# Real fragment of Redfin's sale-history table — mixes a current list,
# a TX non-disclosure sold row, a contingent row, and a prior list.
SAMPLE_HISTORY_HTML = (
    '<div class="BasicTable__row hasSqFt solo">'
    '<div class="BasicTable__col date">Apr 30, 2026</div>'
    '<div class="BasicTable__col event">Listed</div>'
    '<div class="BasicTable__col price">$1,049,000'
    '<p class="subtext">$<!-- -->262<!-- -->/sq ft</p></div></div>'

    '<div class="BasicTable__row solo">'
    '<div class="BasicTable__col date">Apr 26, 2022</div>'
    '<div class="BasicTable__col event">Sold</div>'
    '<div class="BasicTable__col price">*</div></div>'

    '<div class="BasicTable__row mid">'
    '<div class="BasicTable__col date">Mar 21, 2022</div>'
    '<div class="BasicTable__col event">Contingent</div>'
    '<div class="BasicTable__col price">—</div></div>'

    '<div class="BasicTable__row hasSqFt last">'
    '<div class="BasicTable__col date">Mar 17, 2022</div>'
    '<div class="BasicTable__col event">Listed</div>'
    '<div class="BasicTable__col price">$999,500'
    '<p class="subtext">$<!-- -->250<!-- -->/sq ft</p></div></div>'
)


class TestParsePriceHistory(unittest.TestCase):
    def test_extracts_four_rows(self):
        history = _parse_price_history(SAMPLE_HISTORY_HTML)
        self.assertEqual(len(history), 4)

    def test_current_listing_price(self):
        h = _parse_price_history(SAMPLE_HISTORY_HTML)
        self.assertEqual(h[0]["date"], "Apr 30, 2026")
        self.assertEqual(h[0]["event"], "Listed")
        self.assertEqual(h[0]["price"], 1049000)
        self.assertEqual(h[0]["price_per_sqft"], 262)

    def test_non_disclosure_sold_flagged(self):
        sold = _parse_price_history(SAMPLE_HISTORY_HTML)[1]
        self.assertEqual(sold["event"], "Sold")
        self.assertIsNone(sold["price"])
        self.assertTrue(sold["non_disclosure"])

    def test_contingent_row(self):
        cont = _parse_price_history(SAMPLE_HISTORY_HTML)[2]
        self.assertEqual(cont["event"], "Contingent")
        self.assertIsNone(cont["price"])


class TestImpliedAppreciation(unittest.TestCase):
    def test_highflyer_actual(self):
        # Two listings ~4.12 years apart, $999,500 → $1,049,000.
        history = _parse_price_history(SAMPLE_HISTORY_HTML)
        result = _implied_list_appreciation(history)
        self.assertIsNotNone(result)
        self.assertEqual(result["from_price"], 999500)
        self.assertEqual(result["to_price"], 1049000)
        # ~4.12 years, ~5% total → ~1.2%/yr
        self.assertAlmostEqual(result["implied_annual_rate"], 0.012, delta=0.005)
        self.assertAlmostEqual(result["years_between"], 4.12, delta=0.05)

    def test_single_listing_returns_none(self):
        history = [
            {"date": "Apr 30, 2026", "event": "Listed", "price": 1049000,
             "price_per_sqft": 262, "non_disclosure": False},
        ]
        self.assertIsNone(_implied_list_appreciation(history))

    def test_no_priced_listings_returns_none(self):
        # Two Sold rows hidden by non-disclosure — no price data to anchor.
        history = [
            {"date": "Apr 26, 2022", "event": "Sold", "price": None,
             "price_per_sqft": None, "non_disclosure": True},
            {"date": "Apr 22, 2022", "event": "Sold", "price": None,
             "price_per_sqft": None, "non_disclosure": True},
        ]
        self.assertIsNone(_implied_list_appreciation(history))


if __name__ == "__main__":
    unittest.main()
