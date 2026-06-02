"""EPA Superfund / CERCLIS sites in the property's county.

Source: EPA EnviroFacts FRS (Facility Registry Service) REST, filtered to
the Superfund program (`pgm_sys_acrnm = SEMS` — Superfund Enterprise
Management System, EPA's system of record for CERCLIS/NPL sites):

    https://data.epa.gov/efservice/frs_program_facility/
        pgm_sys_acrnm/SEMS/state_code/<ST>/county_name/<COUNTY>/JSON

No auth. The FRS program table doesn't carry reliable per-site lat/lon,
so we scope to the property's county (like the ZIP-scoped NFIP fetcher)
and report a count plus representative site names. A non-zero count is a
prompt for environmental due diligence; zero is a genuine clean signal.

SEMS spans active, archived, NPL and non-NPL CERCLIS sites, so a count
in a large urban county can be high and mostly historical/minor — the
report should treat this as "look closer", not "this property is
contaminated".
"""
from __future__ import annotations

from urllib.parse import quote

import httpx

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult, Source

EFSERVICE = "https://data.epa.gov/efservice"
PROGRAM = "SEMS"
NAME_CAP = 12


def dedupe_sites(rows: list[dict]) -> list[dict]:
    """Unique sites by registry_id, keeping a clean primary_name.

    Returns [{"name": str, "id": str}, ...] in first-seen order, skipping
    rows with no usable name.
    """
    seen: set[str] = set()
    out: list[dict] = []
    for row in rows:
        rid = str(row.get("registry_id") or row.get("pgm_sys_id") or "").strip()
        name = (row.get("primary_name") or "").strip()
        if not name:
            continue
        key = rid or name.upper()
        if key in seen:
            continue
        seen.add(key)
        out.append({"name": name, "id": rid})
    return out


def summarize(rows: list[dict], cap: int = NAME_CAP) -> dict:
    """Count of distinct Superfund sites plus up to `cap` representative names."""
    sites = dedupe_sites(rows)
    return {
        "count": len(sites),
        "names": [s["name"] for s in sites[:cap]],
    }


class EpaSuperfundSource(Source):
    name = "epa_superfund"

    def _url(self, state: str, county: str) -> str:
        # EnviroFacts is path-style; county names can contain spaces.
        return (
            f"{EFSERVICE}/frs_program_facility"
            f"/pgm_sys_acrnm/{PROGRAM}"
            f"/state_code/{quote(state)}"
            f"/county_name/{quote(county.upper())}"
            f"/JSON"
        )

    def fetch(self, address: Address) -> FetchResult:
        state = (address.state_abbr or "").upper()
        county = (address.county_name or "").strip()
        if not state or not county:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"EPA Superfund: need state + county, got "
                      f"state={state!r} county={county!r}.",
            )

        url = self._url(state, county)
        try:
            r = httpx.get(url, timeout=30.0)
            r.raise_for_status()
            rows = r.json()
        except (httpx.HTTPError, ValueError) as e:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"EPA Superfund fetch failed: {e}",
            )

        # EnviroFacts signals an unknown table / bad filter as a dict with
        # an "error" key instead of a list of rows.
        if isinstance(rows, dict) and "error" in rows:
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error=f"EPA Superfund API error: {rows['error']}",
            )
        if not isinstance(rows, list):
            return FetchResult(
                source_name=self.name, address=address, facts={},
                error="EPA Superfund: unexpected response shape.",
            )

        summary = summarize(rows)
        facts: dict[str, Fact] = {}

        facts["superfund_site_count"] = Fact(
            value=summary["count"], source=self.name, raw_ref=url,
            note=f"CERCLIS/SEMS sites in {county} County, {state} (county-wide, "
                 f"includes active + archived)",
        )
        if summary["names"]:
            note = f"up to {NAME_CAP} representative names"
            if summary["count"] > len(summary["names"]):
                note += f" of {summary['count']}"
            facts["superfund_sites"] = Fact(
                value=summary["names"], source=self.name, raw_ref=url, note=note,
            )

        return FetchResult(
            source_name=self.name, address=address, facts=facts,
            raw={"state": state, "county": county, "row_count": len(rows)},
        )
