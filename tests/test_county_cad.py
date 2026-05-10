"""County CAD registry + adapter base-class tests (no network)."""
import unittest

from pipeline.common.address import Address
from pipeline.fetch.county import (
    CountyCADSource,
    get_cad_source,
    register,
    supported_counties,
)
from pipeline.fetch.county._arcgis import ArcGISParcelCAD
from pipeline.fetch.county.tx_denton import DentonTxCAD


def _addr(state="48", county="121", county_name="Denton") -> Address:
    return Address(
        raw="x", matched="x",
        lat=33.15, lon=-97.13,
        state_fips=state, county_fips=county,
        tract_fips="020100", block_fips="0000",
        state_abbr="TX", county_name=county_name, zip="76208",
    )


class TestRegistry(unittest.TestCase):
    def test_denton_registered(self):
        self.assertIn("48121", supported_counties())

    def test_get_cad_for_denton(self):
        adapter = get_cad_source(_addr())
        self.assertIsNotNone(adapter)
        self.assertIsInstance(adapter, DentonTxCAD)

    def test_unregistered_returns_none(self):
        # Loving County, TX (FIPS 48301) — population <100, no CAD adapter
        # planned. Use a stable nonexistent county for this test.
        adapter = get_cad_source(_addr(state="48", county="301", county_name="Loving"))
        self.assertIsNone(adapter)

    def test_register_validates_fips(self):
        with self.assertRaises(ValueError):
            register("48", DentonTxCAD)
        with self.assertRaises(ValueError):
            register(48121, DentonTxCAD)  # type: ignore[arg-type]


class TestArcGISBase(unittest.TestCase):
    def test_attr_map_lookup_case_insensitive(self):
        d = DentonTxCAD()
        attrs = {"Total_Appraised_Value": 425000, "owner_name": "DOE, JANE"}
        self.assertEqual(d._pick(attrs, "tax_assessed_value"), 425000)
        self.assertEqual(d._pick(attrs, "owner_name"), "DOE, JANE")
        self.assertIsNone(d._pick(attrs, "last_sale_price"))

    def test_unconfigured_service_url_returns_clean_error(self):
        class BareCAD(ArcGISParcelCAD):
            name = "bare"
            full_county_fips = "99999"
            county_label = "Bare County"
            service_url = ""
            attr_map = {}

        result = BareCAD().fetch(_addr())
        self.assertFalse(result.ok)
        self.assertIn("service_url not configured", result.error or "")

    def test_tx_subclass_omits_sale_price(self):
        # Even if the layer happened to ship a sale price, TX adapters
        # must not surface it (non-disclosure state).
        d = DentonTxCAD()
        self.assertFalse(d.sale_price_disclosed)


if __name__ == "__main__":
    unittest.main()
