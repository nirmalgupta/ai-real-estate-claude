"""Pure-logic tests for USGS hazard interpolation (no network)."""
import math
import unittest

from pipeline.fetch.usgs_eq import (
    EXCEEDANCE_PROB,
    RETURN_PERIOD_YEARS,
    TARGET_AFE,
    _interp_loglog,
    _parse_curve,
)


class TestTargetAFE(unittest.TestCase):
    def test_2pct_50yr_value(self):
        # 2% in 50yr → annual freq ~ 0.000404
        expected = -math.log(1 - EXCEEDANCE_PROB) / RETURN_PERIOD_YEARS
        self.assertAlmostEqual(TARGET_AFE, expected, places=6)
        self.assertAlmostEqual(TARGET_AFE, 4.04e-4, delta=1e-5)


class TestLogLogInterp(unittest.TestCase):
    def test_target_above_top_returns_none(self):
        curve = [(0.1, 0.001), (0.2, 0.0005)]
        self.assertIsNone(_interp_loglog(curve, 0.01))   # target_y above range

    def test_target_below_bottom_returns_none(self):
        curve = [(0.1, 0.001), (0.2, 0.0005)]
        self.assertIsNone(_interp_loglog(curve, 1e-6))

    def test_interpolation_midpoint(self):
        # Pure log-log line: y = a*x^b. Pick x in [0.1, 0.4], y values from
        # f(x) = 1 / x^2 (so y(0.1)=100, y(0.4)=6.25). Target y=25 → x=0.2.
        curve = [(0.1, 100.0), (0.4, 6.25)]
        x = _interp_loglog(curve, 25.0)
        self.assertIsNotNone(x)
        self.assertAlmostEqual(x, 0.2, places=4)

    def test_empty_curve(self):
        self.assertIsNone(_interp_loglog([], 0.0004))


class TestParseCurve(unittest.TestCase):
    def test_simple_response(self):
        payload = {
            "response": [{
                "metadata": {"imt": "PGA"},
                "data": [{
                    "component": "Total",
                    "xvalues": [0.05, 0.1, 0.2],
                    "yvalues": [0.01, 0.001, 0.0001],
                }],
            }],
        }
        self.assertEqual(
            _parse_curve(payload),
            [(0.05, 0.01), (0.1, 0.001), (0.2, 0.0001)],
        )

    def test_skips_non_pga_response(self):
        payload = {"response": [{"metadata": {"imt": "SA0P2"}, "data": []}]}
        self.assertEqual(_parse_curve(payload), [])

    def test_garbage_returns_empty(self):
        self.assertEqual(_parse_curve(None), [])
        self.assertEqual(_parse_curve({}), [])
        self.assertEqual(_parse_curve({"response": "nope"}), [])


if __name__ == "__main__":
    unittest.main()
