"""Pure-logic tests for NCES helpers (no network)."""
import unittest

from pipeline.fetch.nces import _classify_level, _haversine_miles, _get


class TestHaversine(unittest.TestCase):
    def test_zero_distance(self):
        self.assertAlmostEqual(_haversine_miles(0, 0, 0, 0), 0.0, places=6)

    def test_one_degree_lat(self):
        # 1 degree of latitude ≈ 69 miles anywhere on Earth.
        d = _haversine_miles(0, 0, 1, 0)
        self.assertAlmostEqual(d, 69.09, delta=0.5)


class TestClassifyLevel(unittest.TestCase):
    def test_elementary(self):
        self.assertEqual(_classify_level("KG", "05"), "elementary")
        self.assertEqual(_classify_level("PK", "04"), "elementary")

    def test_middle(self):
        self.assertEqual(_classify_level("06", "08"), "middle")

    def test_high(self):
        self.assertEqual(_classify_level("09", "12"), "high")

    def test_other(self):
        self.assertEqual(_classify_level(None, None), "other")
        self.assertEqual(_classify_level("PK", "UG"), "other")


class TestGet(unittest.TestCase):
    def test_case_insensitive_priority(self):
        attrs = {"NAME": "ALPHA", "Sch_Name": "BETA"}
        self.assertEqual(_get(attrs, "NAME", "SCH_NAME"), "ALPHA")

    def test_falls_back_to_second_key(self):
        attrs = {"SCH_NAME": "GAMMA"}
        self.assertEqual(_get(attrs, "NAME", "SCH_NAME"), "GAMMA")

    def test_missing_returns_none(self):
        self.assertIsNone(_get({"FOO": 1}, "NAME"))

    def test_blank_treated_as_missing(self):
        self.assertIsNone(_get({"NAME": ""}, "NAME"))


if __name__ == "__main__":
    unittest.main()
