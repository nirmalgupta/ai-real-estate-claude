"""Pure-logic tests for NOAA SPC CSV-counting helpers (no network)."""
import unittest

from pipeline.common.address import Address
from pipeline.fetch.noaa_spc import (
    HAIL_COLS,
    TORN_COLS,
    WIND_COLS,
    _count_in_csv,
    _haversine_miles,
)


def _addr() -> Address:
    return Address(
        raw="x", matched="x", lat=33.0, lon=-97.0,
        state_fips="48", county_fips="121",
        tract_fips="000000", block_fips="0000",
        state_abbr="TX", county_name="Denton", zip="76208",
    )


def _torn_csv_row(year: int, mag: float, slat: float, slon: float) -> str:
    """Build a row matching the SPC torn CSV column layout."""
    cells = [""] * 30
    cells[TORN_COLS["yr"]] = str(year)
    cells[TORN_COLS["mag"]] = str(mag)
    cells[TORN_COLS["slat"]] = str(slat)
    cells[TORN_COLS["slon"]] = str(slon)
    return ",".join(cells)


HEADER = ",".join([f"c{i}" for i in range(30)]) + "\n"


class TestHaversine(unittest.TestCase):
    def test_zero(self):
        self.assertAlmostEqual(_haversine_miles(0, 0, 0, 0), 0.0, places=6)


class TestCountInCsv(unittest.TestCase):
    def test_within_radius_and_mag(self):
        # Lat 33.0, lon -97.0 — same point as the address. Magnitude 2 (EF2).
        body = HEADER + _torn_csv_row(2023, 2, 33.0, -97.0) + "\n"
        self.assertEqual(_count_in_csv(body, TORN_COLS, _addr(), mag_min=1.0), 1)

    def test_below_mag_threshold_excluded(self):
        # EF0 — below the EF1+ threshold.
        body = HEADER + _torn_csv_row(2023, 0, 33.0, -97.0) + "\n"
        self.assertEqual(_count_in_csv(body, TORN_COLS, _addr(), mag_min=1.0), 0)

    def test_outside_radius_excluded(self):
        # 5 degrees lat ≈ 345 miles away.
        body = HEADER + _torn_csv_row(2023, 3, 38.0, -97.0) + "\n"
        self.assertEqual(_count_in_csv(body, TORN_COLS, _addr(), mag_min=1.0), 0)

    def test_zero_lat_lon_skipped(self):
        # Some SPC rows have 0/0 placeholders — must not be counted as
        # "near (0,0)" when the address is far from there.
        body = HEADER + _torn_csv_row(2023, 3, 0.0, 0.0) + "\n"
        self.assertEqual(_count_in_csv(body, TORN_COLS, _addr(), mag_min=1.0), 0)

    def test_hail_wind_share_layout(self):
        # The cols dicts intentionally mirror the same indexes; assert it.
        self.assertEqual(HAIL_COLS, TORN_COLS)
        self.assertEqual(WIND_COLS, TORN_COLS)


if __name__ == "__main__":
    unittest.main()
