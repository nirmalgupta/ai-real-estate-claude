"""Logic tests for the DOT AADT fetcher (no network)."""
import unittest

from pipeline.fetch.dot_aadt import (
    envelope,
    functional_class_label,
    pick_busiest,
    _road_label,
)


class TestFunctionalClass(unittest.TestCase):
    def test_known_codes(self):
        self.assertEqual(functional_class_label(1), "Interstate")
        self.assertEqual(functional_class_label(7), "Local")

    def test_string_code_coerced(self):
        self.assertEqual(functional_class_label("4"), "Minor Arterial")

    def test_unknown_returns_none(self):
        self.assertIsNone(functional_class_label(99))
        self.assertIsNone(functional_class_label(None))
        self.assertIsNone(functional_class_label("x"))


class TestEnvelope(unittest.TestCase):
    def test_box_brackets_the_point(self):
        xmin, ymin, xmax, ymax = envelope(33.15, -96.82, 1.0)
        self.assertLess(xmin, -96.82)
        self.assertGreater(xmax, -96.82)
        self.assertLess(ymin, 33.15)
        self.assertGreater(ymax, 33.15)

    def test_latitude_half_width_is_one_mile(self):
        _, ymin, _, ymax = envelope(0.0, 0.0, 1.0)
        # 1 mile half-width ≈ 1/69 degree each side.
        self.assertAlmostEqual(ymax - ymin, 2 / 69.0, places=4)

    def test_longitude_widens_with_latitude(self):
        # At higher latitude the lon span (in degrees) must grow.
        eq = envelope(0.0, 0.0, 1.0)
        hi = envelope(60.0, 0.0, 1.0)
        eq_span = eq[2] - eq[0]
        hi_span = hi[2] - hi[0]
        self.assertGreater(hi_span, eq_span)

    def test_pole_guard_does_not_divide_by_zero(self):
        # cos(90°) == 0; the guard must keep this finite.
        box = envelope(90.0, 0.0, 1.0)
        self.assertTrue(all(isinstance(v, float) for v in box))


class TestPickBusiest(unittest.TestCase):
    def test_picks_max_aadt(self):
        feats = [
            {"attributes": {"aadt": 1200, "routename": "Main"}},
            {"attributes": {"aadt": 280000, "routename": "35E"}},
            {"attributes": {"aadt": 5400, "routename": "FM 423"}},
        ]
        best = pick_busiest(feats)
        self.assertEqual(best["routename"], "35E")

    def test_ignores_null_aadt(self):
        feats = [
            {"attributes": {"aadt": None, "routename": "Quiet St"}},
            {"attributes": {"aadt": 800, "routename": "Side Rd"}},
        ]
        self.assertEqual(pick_busiest(feats)["routename"], "Side Rd")

    def test_empty_returns_none(self):
        self.assertIsNone(pick_busiest([]))
        self.assertIsNone(pick_busiest([{"attributes": {"aadt": None}}]))


class TestRoadLabel(unittest.TestCase):
    def test_prefers_routename(self):
        self.assertEqual(
            _road_label({"routename": "35E", "route_id": "IH0035E-KG"}), "35E"
        )

    def test_falls_back_to_route_id(self):
        self.assertEqual(
            _road_label({"routename": "  ", "route_id": "IH0035E-KG"}), "IH0035E-KG"
        )

    def test_none_when_both_missing(self):
        self.assertIsNone(_road_label({"routename": None, "route_id": ""}))


if __name__ == "__main__":
    unittest.main()
