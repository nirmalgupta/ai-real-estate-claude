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


def composite_score(computed: dict, facts: dict) -> dict:
    """Heuristic 0-100 score from the deterministic numbers.

    Subscores (each 0-100):
      cash_flow:       cap_rate-driven; >5% great, <2% bad
      appreciation:    7-yr CAGR; >6% great, <2% bad
      affordability:   list_price vs ACS tract median home value
      flood:           FEMA zone X = 100, AE/A = 30, V = 0
    """
    cap = computed.get("cash_flow", {}).get("cap_rate", 0)
    # Use IRR for the appreciation subscore. If IRR is undefined (no sign
    # change in cash flow), treat it as a deeply negative rate for scoring.
    irr_val = computed.get("buy_hold", {}).get("irr")
    cagr = irr_val if irr_val is not None else -0.20
    list_price = computed.get("inputs", {}).get("list_price", 0) or 0
    median_home_value = facts.get("median_home_value") or 0
    flood_zone = (facts.get("flood_zone") or "").split()[0] if facts.get("flood_zone") else ""

    cash_flow_score = max(0, min(100, (cap * 100 - 1) * 25))
    appreciation_score = max(0, min(100, (cagr * 100 - 1) * 20))
    if median_home_value > 0:
        ratio = list_price / median_home_value
        # 1.0 = priced like the tract, 2.0 = double, 0.5 = half
        if ratio < 1.5:
            affordability = 100
        elif ratio < 2.5:
            affordability = 70
        elif ratio < 4.0:
            affordability = 40
        else:
            affordability = 20
    else:
        affordability = 50
    flood_score = {
        "X": 95, "B": 70, "C": 90, "AE": 30, "A": 30,
        "AH": 25, "AO": 25, "VE": 5, "V": 5, "D": 50,
    }.get(flood_zone, 50)

    weights = {
        "cash_flow": 0.30,
        "appreciation": 0.20,
        "affordability": 0.30,
        "flood": 0.20,
    }
    subs = {
        "cash_flow": round(cash_flow_score, 1),
        "appreciation": round(appreciation_score, 1),
        "affordability": affordability,
        "flood": flood_score,
    }
    composite = sum(subs[k] * weights[k] for k in weights)
    grade = ("A+" if composite >= 90 else "A" if composite >= 80
             else "B" if composite >= 65 else "C" if composite >= 50
             else "D" if composite >= 35 else "F")
    signal = ("Strong Buy" if composite >= 80 else "Buy" if composite >= 65
              else "Hold" if composite >= 50 else "Watch" if composite >= 35
              else "Avoid")

    return {
        "score": round(composite, 1),
        "grade": grade,
        "signal": signal,
        "subscores": subs,
        "weights": weights,
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

    # Find drafted sections in numeric order
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
    for k in ("cash_flow", "appreciation", "affordability", "flood"):
        label = k.replace("_", " ").title()
        lines.append(f"| {label} | {score['subscores'][k]:.0f}/100 "
                     f"| {int(score['weights'][k] * 100)}% |")
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
