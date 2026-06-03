"""Chatham County, NC — Tax Office.

FIPS 37037. Pittsboro, Siler City, Goldston.

Public endpoint: Chatham publishes a public ArcGIS REST stack on
`gisservices.chathamcountync.gov/opendataagol`. The CAMA-parcel polygon
layer carries owner, FMV/ASV, acreage, legal description and parcel id —
no token, spatial point queries supported:

    gisservices.chathamcountync.gov/.../Cadastral/Chatham_CamaParcels/MapServer/0

NC is a disclosure state, so sale price/date are public. They — plus
year-built/living-area — live in two geometry-less companion tables
keyed by the (zero-padded) parcel number (`parcel_Number`, capital N):

    Chatham_PropertySales         → sale price + date (multiple rows/parcel)
    Chatham_PropertyImprovements  → year built + living area (per structure)

After the primary spatial query, this adapter does two best-effort
attribute-keyed lookups: the latest *valid arms-length* sale (filtering
out correction/non-arms-length deeds, which carry price 0 and
`valid_sale_flag='N'`) and the largest structure's year built + living
area. Either failing leaves the primary parcel result untouched.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult
from pipeline.fetch.county import register
from pipeline.fetch.county._nc_base import NcParcelCAD


def _to_int(v: Any) -> int | None:
    """Coerce string/float numerics to int; None on junk/empty."""
    if v in (None, "", " "):
        return None
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return None


def _epoch_ms_to_date(ms: Any) -> str | None:
    """ArcGIS epoch-ms Date → ISO 'YYYY-MM-DD'. None for junk/placeholders."""
    if not isinstance(ms, (int, float)):
        return None
    try:
        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
    if dt.year < 1900:        # 12/30/1899 = DEVNET "unknown" placeholder
        return None
    return dt.date().isoformat()


def _pick_latest_valid_sale(rows: list[dict]) -> dict | None:
    """Most recent arms-length sale: valid_sale_flag='Y' and a real price."""
    best: dict | None = None
    best_when: float | None = None
    for r in rows:
        if str(r.get("valid_sale_flag", "")).upper() != "Y":
            continue
        price = _to_int(r.get("gross_selling_price") or r.get("net_selling_price"))
        if not price or price <= 0:
            continue
        when = r.get("date_of_sale")
        if not isinstance(when, (int, float)):
            continue
        if best_when is None or when > best_when:
            best_when, best = when, r
    return best


def _pick_primary_structure(rows: list[dict]) -> dict | None:
    """The main dwelling: the structure with the largest living area."""
    best: dict | None = None
    best_area = -1
    for r in rows:
        area = _to_int(r.get("gross_living_area")) or 0
        if area > best_area:
            best_area, best = area, r
    return best


def _parse_sale(sale: dict) -> dict[str, Any]:
    out: dict[str, Any] = {}
    price = _to_int(sale.get("gross_selling_price") or sale.get("net_selling_price"))
    if price and price > 0:
        out["last_sale_price"] = price
    when = _epoch_ms_to_date(sale.get("date_of_sale"))
    if when:
        out["last_sale_date"] = when
    return out


def _parse_structure(struct: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    yb = _to_int(struct.get("year_built"))
    if yb and yb > 1700:
        out["year_built_cad"] = yb
    la = _to_int(struct.get("gross_living_area"))
    if la and la > 0:
        out["living_area_sqft_cad"] = la
    return out


class ChathamNcCAD(NcParcelCAD):
    name = "nc_chatham_cad"
    full_county_fips = "37037"
    county_label = "Chatham County, NC"

    _BASE = (
        "https://gisservices.chathamcountync.gov/opendataagol/rest/services/"
        "Cadastral"
    )
    service_url = f"{_BASE}/Chatham_CamaParcels/MapServer/0"
    sales_url = f"{_BASE}/Chatham_PropertySales/MapServer/0"
    improvements_url = f"{_BASE}/Chatham_PropertyImprovements/MapServer/0"
    sales_note = "Chatham DEVNET sales — latest valid arms-length deed"
    improvements_note = "Chatham DEVNET structures — primary dwelling"

    attr_map = {
        "tax_market_value":   ["jan1_total_FMV"],
        "tax_assessed_value": ["jan1_total_ASV"],
        "tax_assessed_year":  ["parcel_year"],
        "lot_size_acres":     ["gross_current_acres"],
        "legal_description":  ["legal_desc1"],
        "owner_name":         ["current_owners"],
        "property_id":        ["parcel_number", "alternate_parcel_number"],
    }

    def _table_query(self, table_url: str, parcel_number: str) -> tuple[list[dict], str]:
        """Best-effort attribute lookup on a companion table. ([], url) on failure."""
        url = f"{table_url}/query"
        params = {
            "f": "json",
            "where": f"parcel_Number='{parcel_number}'",
            "outFields": "*",
            "returnGeometry": "false",
        }
        try:
            r = httpx.get(url, params=params, timeout=self.timeout_s)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError):
            return [], url
        features = data.get("features") if isinstance(data, dict) else None
        if not isinstance(features, list):
            return [], url
        return [f.get("attributes") or {} for f in features], url

    def fetch(self, address: Address) -> FetchResult:
        result = super().fetch(address)
        if not result.ok:
            return result

        pid = result.facts.get("property_id")
        parcel_number = str(pid.value).strip() if pid is not None else ""
        if not parcel_number:
            return result

        sale_rows, sale_url = self._table_query(self.sales_url, parcel_number)
        sale = _pick_latest_valid_sale(sale_rows)
        if sale:
            for key, value in _parse_sale(sale).items():
                result.facts[key] = Fact(
                    value=value, source=self.name, raw_ref=sale_url,
                    note=self.sales_note,
                )

        imp_rows, imp_url = self._table_query(self.improvements_url, parcel_number)
        struct = _pick_primary_structure(imp_rows)
        if struct:
            for key, value in _parse_structure(struct).items():
                result.facts[key] = Fact(
                    value=value, source=self.name, raw_ref=imp_url,
                    note=self.improvements_note,
                )

        return result


register("37037", ChathamNcCAD)
