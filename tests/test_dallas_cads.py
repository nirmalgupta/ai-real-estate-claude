"""DFW remaining-3 CAD adapter registration tests."""
import unittest

from pipeline.common.address import Address
from pipeline.fetch.county import get_cad_source, supported_counties
from pipeline.fetch.county._tx_base import TxParcelCAD
from pipeline.fetch.county.tx_collin import CollinTxCAD
from pipeline.fetch.county.tx_dallas import DallasTxCAD
from pipeline.fetch.county.tx_tarrant import TarrantTxCAD


DFW_REMAINING = {
    "48113": DallasTxCAD,
    "48439": TarrantTxCAD,
    "48085": CollinTxCAD,
}


def _addr_for(county_fips: str) -> Address:
    return Address(
        raw="x", matched="x", lat=32.78, lon=-96.80,
        state_fips=county_fips[:2], county_fips=county_fips[2:],
        tract_fips="000000", block_fips="0000",
        state_abbr="TX", county_name="X", zip="75201",
    )


class TestDFWRegistry(unittest.TestCase):
    def test_all_three_registered(self):
        for fips in DFW_REMAINING:
            self.assertIn(fips, supported_counties())

    def test_resolution(self):
        for fips, cls in DFW_REMAINING.items():
            self.assertIsInstance(get_cad_source(_addr_for(fips)), cls)

    def test_tx_invariants(self):
        # Tarrant has no public REST endpoint identified yet; its
        # service_url is intentionally empty and the adapter returns a
        # clean "service_url not configured" error. Don't require a
        # populated URL.
        for cls in DFW_REMAINING.values():
            self.assertTrue(issubclass(cls, TxParcelCAD))
            self.assertFalse(cls.sale_price_disclosed)


if __name__ == "__main__":
    unittest.main()
