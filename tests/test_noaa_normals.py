"""Logic tests for NOAA Climate Normals fetcher (no network)."""
import unittest

from pipeline.fetch.noaa_normals import (
    _haversine_miles,
    _nearest_stations,
    _parse_inventory,
    _parse_station_csv,
)


# Real lines from the NCEI inventory_30yr.txt (Austin TX area).
SAMPLE_INVENTORY = (
    "AQC00914000 -14.3167 -170.7667  408.4 AS AASUFOU                                     \n"
    "USW00013904  30.1830  -97.6797  149.0 TX AUSTIN BERGSTROM AP             GSN     91997\n"
    "USW00013958  30.2900  -97.7400  189.0 TX AUSTIN MABRY                                  \n"
    "USC00410428  30.5500  -97.8333  280.0 TX AUSTIN CAMP MABRY                              \n"
)


SAMPLE_STATION_CSV = (
    "STATION,DATE,ANN-PRCP-NORMAL,ANN-TAVG-NORMAL,ANN-TMAX-AVGNDS-GRTH090,ANN-TMIN-AVGNDS-LSTH032\n"
    "USW00013904,1,35.57,68.4,123.5,33.0\n"
)


SAMPLE_PARTIAL_CSV = (
    "STATION,DATE,ANN-PRCP-NORMAL,ANN-TAVG-NORMAL\n"
    "USW00099999,1,28.10,\n"
)


class TestParseInventory(unittest.TestCase):
    def test_picks_up_all_rows(self):
        rows = _parse_inventory(SAMPLE_INVENTORY)
        self.assertEqual(len(rows), 4)

    def test_extracts_station_fields(self):
        rows = _parse_inventory(SAMPLE_INVENTORY)
        austin = next(r for r in rows if r["id"] == "USW00013904")
        self.assertAlmostEqual(austin["lat"], 30.1830, places=3)
        self.assertAlmostEqual(austin["lon"], -97.6797, places=3)
        self.assertEqual(austin["state"], "TX")

    def test_handles_short_lines(self):
        rows = _parse_inventory("\nABC\n")
        self.assertEqual(rows, [])


class TestNearestStations(unittest.TestCase):
    def test_orders_by_distance(self):
        stations = _parse_inventory(SAMPLE_INVENTORY)
        # Frisco, TX is ~200 mi from Austin
        results = _nearest_stations(stations, 33.1500, -96.8244, k=3)
        # All TX stations should come back before American Samoa
        for _, s in results:
            self.assertEqual(s["state"], "TX")


class TestHaversine(unittest.TestCase):
    def test_known_distance(self):
        # NYC <-> LA ≈ 2451 mi (great-circle)
        d = _haversine_miles(40.7128, -74.0060, 34.0522, -118.2437)
        self.assertAlmostEqual(d, 2451, delta=10)


class TestParseStationCsv(unittest.TestCase):
    def test_extracts_all_four_fields(self):
        out = _parse_station_csv(SAMPLE_STATION_CSV)
        self.assertEqual(out["annual_mean_temp_f"], 68.4)
        self.assertEqual(out["annual_precip_inches"], 35.57)
        self.assertEqual(out["days_above_90f"], 123.5)
        self.assertEqual(out["days_below_32f"], 33.0)

    def test_missing_column_returns_none(self):
        # Partial CSV with no temperature averages
        out = _parse_station_csv(SAMPLE_PARTIAL_CSV)
        self.assertEqual(out["annual_precip_inches"], 28.10)
        self.assertIsNone(out["annual_mean_temp_f"])
        self.assertIsNone(out["days_above_90f"])

    def test_blank_value_returns_none(self):
        # Has the column but the cell is blank
        out = _parse_station_csv(SAMPLE_PARTIAL_CSV)
        self.assertIsNone(out["annual_mean_temp_f"])


if __name__ == "__main__":
    unittest.main()
