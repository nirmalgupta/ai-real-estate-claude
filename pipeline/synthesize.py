"""Stitch section drafts into PROPERTY-ANALYSIS.md.

Reads:
    reports/<slug>/sections/*.md   (drafts you wrote during Phase D)
    reports/<slug>/computed.json   (deterministic numbers)
    wiki/properties/<slug>.md      (raw facts, for the snapshot)

Writes:
    reports/<slug>/PROPERTY-ANALYSIS.md
    reports/<slug>/composite_score.json   (used by the PDF generator)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from pipeline.analyze.wiki_loader import load_wiki_facts

DEFAULT_REPO = Path(__file__).resolve().parent.parent
DEFAULT_WIKI = DEFAULT_REPO / "wiki"
DEFAULT_REPORTS = DEFAULT_REPO / "reports"


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _score_cash_flow(computed: dict, _facts: dict) -> float | None:
    cap = computed.get("cash_flow", {}).get("cap_rate")
    if cap is None:
        return None
    return _clamp((cap * 100 - 1) * 25)


def _score_cash_on_cash(computed: dict, _facts: dict) -> float | None:
    coc = computed.get("cash_flow", {}).get("cash_on_cash")
    if coc is None:
        return None
    return _clamp((coc * 100 - 2) * 20)


def _score_irr(computed: dict, _facts: dict) -> float | None:
    """Use the 5%-appreciation row from the sensitivity table — that's
    the closest thing to a single canonical 'reasonable assumption' IRR."""
    sens = computed.get("buy_hold", {}).get("sensitivity") or []
    row = next((r for r in sens if abs(r.get("appreciation_rate", 0) - 0.05) < 0.001), None)
    irr = row.get("irr") if row else computed.get("buy_hold", {}).get("irr")
    if irr is None:
        return None
    return _clamp((irr * 100 - 1) * 14)


def _score_appreciation_history(_computed: dict, facts: dict) -> float | None:
    """Penalize properties whose own historical list-to-list appreciation
    runs below the 5% baseline — that's an investor's reality check that
    forward 5% projections may be optimistic for this specific home."""
    implied = facts.get("redfin_implied_list_appreciation")
    if not isinstance(implied, dict):
        return None
    rate = implied.get("implied_annual_rate")
    if rate is None:
        return None
    # 0% → 30, 3% → 65, 5% → 85, 8% → 100
    return _clamp(rate * 100 * 12 + 30)


def _score_tax_burden(computed: dict, facts: dict) -> float | None:
    """Penalize properties where the upcoming tax reassessment hits hard.
    Compares (annual_property_tax / list_price) to a typical 1.5%."""
    tax = computed.get("inputs", {}).get("annual_property_tax")
    list_price = computed.get("inputs", {}).get("list_price")
    if not tax or not list_price:
        return None
    rate_pct = tax / list_price * 100
    # 1.0% → 100, 1.5% → 80, 2.0% → 60, 2.5% → 40, 3.0% → 20
    return _clamp(100 - max(0, rate_pct - 1.0) * 40)


def _score_flood(_computed: dict, facts: dict) -> float | None:
    zone = facts.get("flood_zone")
    if not zone:
        return None
    z = str(zone).split()[0].upper()
    table = {
        "X": 95, "B": 80, "C": 90, "D": 50,
        "A": 30, "AE": 30, "AH": 30, "AO": 30, "AR": 30,
        "V": 5, "VE": 5,
    }
    # NFIP claims activity in the ZIP further degrades the score
    score = table.get(z, 60)
    nfip = facts.get("nfip_claims_count_10yr") or 0
    if nfip:
        # 50+ claims/decade in ZIP is a meaningful flood-frequency signal
        score = _clamp(score - min(40, nfip * 0.5))
    return _clamp(score)


def _score_storms(_computed: dict, facts: dict) -> float | None:
    """Combined hail + tornado history in last 10 years."""
    hail = facts.get("hail_within_10mi_10yr")
    torn = facts.get("tornadoes_within_10mi_10yr")
    if hail is None and torn is None:
        return None
    h = hail or 0
    t = torn or 0
    # 0 events = 100; each hail event -1; each tornado -3
    return _clamp(100 - h - t * 3)


def _score_seismic(_computed: dict, facts: dict) -> float | None:
    pga = facts.get("seismic_pga_2pct_50yr")
    if pga is None:
        return None
    # 0.05g (low seismic) → 95, 0.3g → 60, 0.6g+ → 20
    return _clamp(100 - pga * 130)


def _score_schools(_computed: dict, facts: dict) -> float | None:
    """Closer is better; pull the nearest distance across elem/middle/high."""
    candidates = [
        facts.get("nearest_elementary_distance_miles"),
        facts.get("nearest_middle_distance_miles"),
        facts.get("nearest_high_distance_miles"),
    ]
    distances = [d for d in candidates if isinstance(d, (int, float))]
    if not distances:
        return None
    avg = sum(distances) / len(distances)
    # 0.5 mi avg = 95; 2 mi = 70; 5+ mi = 30
    return _clamp(100 - avg * 14)


def _score_walkability(_computed: dict, facts: dict) -> float | None:
    """Use supermarket distance as the keystone walk signal; back off to
    pharmacy / convenience if super is missing."""
    candidates = [
        facts.get("nearest_supermarket_miles"),
        facts.get("nearest_pharmacy_miles"),
        facts.get("nearest_convenience_miles"),
    ]
    distances = [d for d in candidates if isinstance(d, (int, float))]
    if not distances:
        return None
    nearest = min(distances)
    # 0.25 mi = 100, 1 mi = 75, 3 mi = 40, 5+ mi = 10
    return _clamp(100 - nearest * 18)


def _score_neighborhood_income(_computed: dict, facts: dict) -> float | None:
    """ACS median household income vs the rough US median (~75k)."""
    inc = facts.get("median_household_income")
    if inc is None:
        return None
    ratio = inc / 75000.0
    # 0.5x = 30, 1.0x = 60, 1.5x = 85, 2.0x+ = 95
    return _clamp(ratio * 50 + 10)


# Signal registry: (key, weight, scorer)
_SIGNALS = (
    ("cash_flow", 0.15, _score_cash_flow),
    ("cash_on_cash", 0.10, _score_cash_on_cash),
    ("appreciation_irr", 0.15, _score_irr),
    ("appreciation_history", 0.09, _score_appreciation_history),
    ("tax_burden", 0.10, _score_tax_burden),
    ("flood", 0.10, _score_flood),
    ("storms", 0.05, _score_storms),
    ("seismic", 0.03, _score_seismic),
    ("schools", 0.10, _score_schools),
    ("walkability", 0.08, _score_walkability),
    ("neighborhood_income", 0.05, _score_neighborhood_income),
)


def composite_score(computed: dict, facts: dict) -> dict:
    """Compute the 0-100 score from every available v2 signal.

    For every signal whose source fact is missing, that signal's weight
    is redistributed proportionally across the remaining signals — a
    property is never penalized for the pipeline's incomplete data.

    Returns:
        {
          score:        weighted average across available signals (0-100)
          grade:        A+/A/B/C/D/F letter mapping
          signal:       Strong Buy / Buy / Hold / Watch / Avoid
          subscores:    {key: float}  raw 0-100 score for each available signal
          weights:      {key: float}  redistributed weight per available signal
          weights_base: {key: float}  original (un-redistributed) weights
          missing:      [key, ...]    signals dropped due to missing facts
        }
    """
    raw: dict[str, float] = {}
    missing: list[str] = []
    base_weights = {k: w for k, w, _ in _SIGNALS}
    for key, _w, scorer in _SIGNALS:
        v = scorer(computed, facts)
        if v is None:
            missing.append(key)
        else:
            raw[key] = round(v, 1)

    if not raw:
        return {
            "score": 0.0, "grade": "F", "signal": "Avoid",
            "subscores": {}, "weights": {},
            "weights_base": base_weights, "missing": missing,
        }

    total_w = sum(base_weights[k] for k in raw)
    weights = {k: round(base_weights[k] / total_w, 4) for k in raw}
    composite = sum(raw[k] * weights[k] for k in raw)

    grade = (
        "A+" if composite >= 90 else "A" if composite >= 80
        else "B" if composite >= 65 else "C" if composite >= 50
        else "D" if composite >= 35 else "F"
    )
    signal = (
        "Strong Buy" if composite >= 80 else "Buy" if composite >= 65
        else "Hold" if composite >= 50 else "Watch" if composite >= 35
        else "Avoid"
    )

    return {
        "score": round(composite, 1),
        "grade": grade,
        "signal": signal,
        "subscores": raw,
        "weights": weights,
        "weights_base": base_weights,
        "missing": missing,
    }


_PRETTY = {
    "cash_flow": "Cap Rate",
    "cash_on_cash": "Cash-on-Cash",
    "appreciation_irr": "7-yr IRR (5%)",
    "appreciation_history": "Historical Appreciation",
    "tax_burden": "Tax Burden",
    "flood": "Flood Risk",
    "storms": "Storm History",
    "seismic": "Seismic",
    "schools": "Schools",
    "walkability": "Walkability",
    "neighborhood_income": "Neighborhood Income",
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("slug", help="Address slug used by run.py")
    p.add_argument("--reports", type=Path, default=DEFAULT_REPORTS)
    p.add_argument("--wiki", type=Path, default=DEFAULT_WIKI)
    args = p.parse_args(argv)

    report_dir = args.reports / args.slug
    sections_dir = report_dir / "sections"
    wiki_page = args.wiki / "properties" / f"{args.slug}.md"
    computed_path = report_dir / "computed.json"

    if not wiki_page.exists():
        print(f"ERROR: wiki page not found: {wiki_page}", file=sys.stderr)
        return 1
    if not computed_path.exists():
        print(f"ERROR: {computed_path} missing — run pipeline.analyze.compute first",
              file=sys.stderr)
        return 1
    if not sections_dir.is_dir():
        print(f"ERROR: no sections in {sections_dir} — draft them in Phase D first",
              file=sys.stderr)
        return 1

    fm, facts = load_wiki_facts(wiki_page)
    computed = json.loads(computed_path.read_text())
    score = composite_score(computed, facts)

    section_files = sorted(sections_dir.glob("*.md"))

    lines = [
        f"# Property Analysis: {fm['address']}",
        "",
        f"**Score:** {score['score']}/100 · "
        f"**Grade:** {score['grade']} · "
        f"**Signal:** {score['signal']}",
        "",
        "> AI-generated estimates. Not financial or investment advice. "
        "Consult a licensed real estate professional.",
        "",
        "## Score Dashboard",
        "| Dimension | Score | Weight |",
        "|---|---|---|",
    ]
    # Dashboard shows each available signal in the order it's registered
    for key in score["subscores"]:
        label = _PRETTY.get(key, key.replace("_", " ").title())
        lines.append(
            f"| {label} | {score['subscores'][key]:.0f}/100 "
            f"| {int(score['weights'][key] * 100)}% |"
        )
    if score["missing"]:
        lines.append("")
        lines.append(
            "_Signals not scored (data missing — weights redistributed): "
            + ", ".join(_PRETTY.get(k, k) for k in score["missing"])
            + "._"
        )
    lines.append("")

    for sf in section_files:
        body = sf.read_text().strip()
        if body:
            lines.append(body)
            lines.append("")

    lines.append("---")
    lines.append(
        f"_Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} "
        f"from {len(section_files)} section drafts + computed.json + wiki facts._"
    )
    lines.append("")

    out_md = report_dir / "PROPERTY-ANALYSIS.md"
    out_md.write_text("\n".join(lines))

    out_score = report_dir / "composite_score.json"
    out_score.write_text(json.dumps(score, indent=2))

    print(f"Wrote {out_md}")
    print(f"Wrote {out_score}")
    print(f"Score: {score['score']}/100 ({score['grade']}, {score['signal']})")
    if score["missing"]:
        print(f"Missing signals: {', '.join(score['missing'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
