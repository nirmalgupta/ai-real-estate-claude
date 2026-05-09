#!/usr/bin/env bash
# Remove AI Real Estate Analyst skills from ~/.claude/
set -euo pipefail

CLAUDE_DIR="${HOME}/.claude"

echo "Removing AI Real Estate Analyst..."

rm -rf "${CLAUDE_DIR}/skills/real-estate"
for d in "${CLAUDE_DIR}/skills/real-estate-"*; do
    [ -d "${d}" ] && rm -rf "${d}"
done

rm -f "${CLAUDE_DIR}/agents/re-comps.md"
rm -f "${CLAUDE_DIR}/agents/re-rental.md"
rm -f "${CLAUDE_DIR}/agents/re-neighborhood.md"
rm -f "${CLAUDE_DIR}/agents/re-investment.md"
rm -f "${CLAUDE_DIR}/agents/re-market.md"

rm -f "${CLAUDE_DIR}/scripts/analyze_property.py"
rm -f "${CLAUDE_DIR}/scripts/score_property.py"
rm -f "${CLAUDE_DIR}/scripts/generate_pdf_report.py"
rm -f "${CLAUDE_DIR}/scripts/mortgage_calculator.py"
rm -f "${CLAUDE_DIR}/scripts/send_imessage.py"
rm -f "${CLAUDE_DIR}/re_complete_config.json"

echo "Done. (reportlab not removed — pip uninstall reportlab if you want)"
