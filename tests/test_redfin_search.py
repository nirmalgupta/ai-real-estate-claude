"""Pure-logic tests for Redfin search helpers (no network)."""
import unittest

from pipeline.search.redfin import _bbox_polygon, _parse_csv


SAMPLE_CSV = """\
SALE TYPE,SOLD DATE,PROPERTY TYPE,ADDRESS,CITY,STATE OR PROVINCE,ZIP OR POSTAL CODE,PRICE,BEDS,BATHS,LOCATION,SQUARE FEET,LOT SIZE,YEAR BUILT,DAYS ON MARKET,$/SQUARE FEET,HOA/MONTH,STATUS,NEXT OPEN HOUSE START TIME,NEXT OPEN HOUSE END TIME,URL (SEE https://www.redfin.com/buy-a-home/comparative-market-analysis FOR INFO ON PRICING),SOURCE,MLS#,FAVORITE,INTERESTED,LATITUDE,LONGITUDE
"In accordance with local MLS rules, some MLS listings are not included in the download"
MLS Listing,,Single Family Residential,5646 Highflyer Hills Trl,Frisco,TX,75036,1049000,5,5.0,Phillips Creek Ranch Ph 4b,4005,8102,2016,10,262,220,Active,,,https://www.redfin.com/TX/Frisco/5646-Highflyer-Hills-Trl-75036/home/104485204,NTREIS,21254752,N,Y,33.1258712,-96.8824252
MLS Listing,,Condo/Co-op,123 Main St #4B,Plano,TX,75074,425000,2,2.0,Downtown,1450,,2018,33,293,310,Active,,,https://www.redfin.com/TX/Plano/sample/home/000,NTREIS,99999,N,N,33.0,-96.7
"""


class TestBboxPolygon(unittest.TestCase):
    def test_polygon_is_closed(self):
        poly = _bbox_polygon(33.0, -97.0, 1.0)
        pts = poly.split(",")
        self.assertEqual(len(pts), 5)
        self.assertEqual(pts[0], pts[-1])

    def test_polygon_size_matches_radius(self):
        # 1-mile half-side → 2 mile total side. lat delta = 1/69 ≈ 0.01449.
        poly = _bbox_polygon(33.0, -97.0, 1.0)
        pts = [p.split() for p in poly.split(",")]
        lats = [float(p[1]) for p in pts]
        self.assertAlmostEqual(max(lats) - min(lats), 2 / 69.0, places=4)

    def test_longitude_shrinks_with_latitude(self):
        # At lat 60° N, 1° longitude is half the distance of at the equator.
        equator = _bbox_polygon(0.0, 0.0, 10.0)
        polar = _bbox_polygon(60.0, 0.0, 10.0)
        eq_lons = [float(p.split()[0]) for p in equator.split(",")]
        po_lons = [float(p.split()[0]) for p in polar.split(",")]
        eq_span = max(eq_lons) - min(eq_lons)
        po_span = max(po_lons) - min(po_lons)
        self.assertGreater(po_span, eq_span * 1.9)


class TestParseCsv(unittest.TestCase):
    def test_skips_mls_notice_row(self):
        listings = _parse_csv(SAMPLE_CSV)
        self.assertEqual(len(listings), 2)

    def test_first_listing_fields(self):
        L = _parse_csv(SAMPLE_CSV)[0]
        self.assertEqual(L.address, "5646 Highflyer Hills Trl")
        self.assertEqual(L.city, "Frisco")
        self.assertEqual(L.zip, "75036")
        self.assertEqual(L.price, 1049000)
        self.assertEqual(L.beds, 5)
        self.assertEqual(L.baths, 5.0)
        self.assertEqual(L.sqft, 4005)
        self.assertEqual(L.lot_sqft, 8102)
        self.assertEqual(L.year_built, 2016)
        self.assertEqual(L.days_on_market, 10)
        self.assertEqual(L.price_per_sqft, 262)
        self.assertEqual(L.hoa_monthly, 220)
        self.assertEqual(L.mls_number, "21254752")
        self.assertEqual(L.lat, 33.1258712)
        self.assertEqual(L.lon, -96.8824252)
        self.assertIn("/TX/Frisco/", L.url)

    def test_missing_lot_handled(self):
        L = _parse_csv(SAMPLE_CSV)[1]
        self.assertIsNone(L.lot_sqft)
        self.assertEqual(L.beds, 2)

    def test_blank_address_row_skipped(self):
        body = "ADDRESS,CITY,STATE OR PROVINCE,ZIP OR POSTAL CODE,PRICE\n,,,,\n"
        self.assertEqual(_parse_csv(body), [])


if __name__ == "__main__":
    unittest.main()
