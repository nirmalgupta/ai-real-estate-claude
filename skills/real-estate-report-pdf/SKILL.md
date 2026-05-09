---
name: real-estate-report-pdf
description: Convert the latest PROPERTY-ANALYSIS.md into a styled PDF report. Trigger on /real-estate-report-pdf or "make a PDF of the report".
---

# Real Estate — PDF Report

## Steps

1. Find the most recent `PROPERTY-ANALYSIS.md` in the cwd. If missing, ask the user to run `/real-estate-analyze` first.
2. Look for `composite_score.json` in the same dir (used for the scorecard graphic).
3. Run:
   ```
   python3 ~/.claude/scripts/generate_pdf_report.py PROPERTY-ANALYSIS.md
   ```
4. Output filename: `PROPERTY-REPORT-<address-slug>-<YYYYMMDD>.pdf`
5. Tell the user the file path.

## Requires

- Python 3.8+
- `reportlab` (`pip install reportlab markdown`)

If `reportlab` isn't installed, tell the user to run `pip install -r ~/.claude/scripts/requirements.txt` and retry.
