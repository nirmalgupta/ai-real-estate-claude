#!/usr/bin/env python3
"""
Read the 5 agent output files in cwd, extract their subscores, and write
composite_score.json with weighted total + grade + signal.

Subscore extraction: looks for a line matching `**<Dimension>: XX/100**` near
the bottom of each agent file.

Usage:
    python3 score_property.py
"""
import json
import re
import sys
from pathlib import Path

WEIGHTS = {
    "comparable value": 0.25,
    "income potential": 0.20,
    "neighborhood quality": 0.20,
    "investment upside": 0.15,
    "market conditions": 0.20,
}

AGENT_FILES = {
    "comparable value": "agent-comps.md",
    "income potential": "agent-rental.md",
    "neighborhood quality": "agent-neighborhood.md",
    "investment upside": "agent-investment.md",
    "market conditions": "agent-market.md",
}

SUBSCORE_RX = re.compile(r"\*\*\s*([A-Za-z &]+?)\s*:\s*(\d+)\s*/\s*100\s*\*\*", re.I)


def extract_subscore(path: Path) -> int | None:
    if not path.exists():
        return None
    text = path.read_text()
    matches = SUBSCORE_RX.findall(text)
    if not matches:
        return None
    # Take the last match (subscore section is at the bottom)
    return int(matches[-1][1])


def grade(score: float) -> str:
    if score >= 90:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    if score >= 50:
        return "D"
    return "F"


def signal(score: float) -> str:
    if score >= 80:
        return "Strong Buy"
    if score >= 70:
        return "Buy"
    if score >= 60:
        return "Hold / Watch"
    if score >= 45:
        return "Caution"
    return "Avoid"


def main():
    cwd = Path.cwd()
    subs = {}
    missing = []
    for dim, fname in AGENT_FILES.items():
        s = extract_subscore(cwd / fname)
        if s is None:
            missing.append(dim)
            subs[dim] = None
        else:
            subs[dim] = s

    # Renormalize weights if any dimensions are missing
    available = {d: s for d, s in subs.items() if s is not None}
    if not available:
        print(json.dumps({"error": "No agent outputs found", "missing": missing}))
        sys.exit(1)

    used_weight = sum(WEIGHTS[d] for d in available)
    composite = sum(s * WEIGHTS[d] for d, s in available.items()) / used_weight

    out = {
        "score": round(composite, 1),
        "grade": grade(composite),
        "signal": signal(composite),
        "subscores": subs,
        "weights": WEIGHTS,
        "missing": missing,
    }
    (cwd / "composite_score.json").write_text(json.dumps(out, indent=2))
    json.dump(out, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
