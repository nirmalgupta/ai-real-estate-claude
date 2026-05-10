#!/usr/bin/env python3
"""
Convert PROPERTY-ANALYSIS.md to a styled PDF report.

Usage:
    python3 generate_pdf_report.py PROPERTY-ANALYSIS.md
    python3 generate_pdf_report.py PROPERTY-ANALYSIS.md -o custom-name.pdf
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    )
except ImportError:
    print("ERROR: reportlab not installed. Run: pip install reportlab", file=sys.stderr)
    sys.exit(1)


# Color palette — match the on-screen scorecard look
NAVY = colors.HexColor("#1f2937")
INDIGO = colors.HexColor("#4f46e5")
GREEN = colors.HexColor("#10b981")
AMBER = colors.HexColor("#f59e0b")
RED = colors.HexColor("#dc2626")
GRAY_BG = colors.HexColor("#f7f7f5")
GRAY_LINE = colors.HexColor("#d4d4d0")
GRAY_TEXT = colors.HexColor("#6b7280")


def slugify(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    return re.sub(r"[\s_-]+", "-", s)[:60]


def grade_color(grade: str):
    return {
        "A+": GREEN, "A": GREEN,
        "B": INDIGO, "C": AMBER,
        "D": RED, "F": RED,
    }.get(grade, GRAY_TEXT)


def parse_markdown(md_text: str) -> list[dict]:
    """Parse markdown into a list of {type, content} blocks for ReportLab."""
    blocks = []
    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("# "):
            blocks.append({"type": "h1", "text": line[2:].strip()})
        elif line.startswith("## "):
            blocks.append({"type": "h2", "text": line[3:].strip()})
        elif line.startswith("### "):
            blocks.append({"type": "h3", "text": line[4:].strip()})
        elif line.startswith("> "):
            blocks.append({"type": "quote", "text": line[2:].strip()})
        elif line.startswith("|"):
            # Collect table
            tbl = []
            while i < len(lines) and lines[i].startswith("|"):
                row = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                tbl.append(row)
                i += 1
            # Drop separator row
            if len(tbl) > 1 and all(re.match(r"^[-: ]+$", c) for c in tbl[1]):
                tbl.pop(1)
            blocks.append({"type": "table", "rows": tbl})
            continue
        elif line.startswith("- ") or line.startswith("* "):
            blocks.append({"type": "bullet", "text": line[2:].strip()})
        elif line.strip() == "":
            blocks.append({"type": "space"})
        else:
            blocks.append({"type": "p", "text": line.strip()})
        i += 1
    return blocks


def render_md_inline(text: str) -> str:
    """Convert markdown bold/italic to ReportLab Paragraph tags."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', text)
    return text


def build_scorecard(score_data: dict, styles) -> Table:
    score = score_data.get("score", 0)
    grade = score_data.get("grade", "?")
    signal_text = score_data.get("signal", "?")

    bar_width = 4.5 * inch
    fill_w = bar_width * (score / 100)

    cells = [
        [Paragraph(f"<b>OVERALL SCORE</b>", styles["small"])],
        [Paragraph(f'<font size="32" color="{grade_color(grade).hexval()}">'
                   f'<b>{score:.0f}</b></font>'
                   f'<font size="14" color="{GRAY_TEXT.hexval()}">/100</font>', styles["normal"])],
        [Paragraph(f'<b>Grade {grade}</b>  ·  {signal_text}', styles["normal"])],
    ]
    t = Table(cells, colWidths=[5 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRAY_BG),
        ("BOX", (0, 0), (-1, -1), 1, GRAY_LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 18),
        ("RIGHTPADDING", (0, 0), (-1, -1), 18),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    return t


def build_table(rows: list[list[str]], styles) -> Table:
    parsed = [[Paragraph(render_md_inline(c), styles["cell"]) for c in row]
              for row in rows]
    n_cols = max(len(r) for r in parsed) if parsed else 1
    col_w = [6.5 * inch / n_cols] * n_cols
    t = Table(parsed, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, GRAY_LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRAY_BG]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def build_pdf(md_path: Path, out_path: Path):
    md_text = md_path.read_text()
    blocks = parse_markdown(md_text)

    score_data = {}
    score_file = md_path.parent / "composite_score.json"
    if score_file.exists():
        try:
            score_data = json.loads(score_file.read_text())
        except json.JSONDecodeError:
            pass

    doc = SimpleDocTemplate(
        str(out_path), pagesize=LETTER,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        title="Property Analysis Report",
    )

    base = getSampleStyleSheet()
    styles = {
        "h1": ParagraphStyle("h1", parent=base["Title"], fontSize=22,
                              textColor=NAVY, spaceAfter=12),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=14,
                              textColor=INDIGO, spaceBefore=18, spaceAfter=6),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontSize=11,
                              textColor=NAVY, spaceBefore=10, spaceAfter=4),
        "normal": ParagraphStyle("normal", parent=base["BodyText"], fontSize=10,
                                  leading=14, textColor=NAVY),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontSize=8,
                                 textColor=GRAY_TEXT),
        "quote": ParagraphStyle("quote", parent=base["BodyText"], fontSize=9,
                                 textColor=GRAY_TEXT, leftIndent=12,
                                 borderPadding=8, italic=True),
        "cell": ParagraphStyle("cell", parent=base["BodyText"], fontSize=9,
                                leading=11),
        "bullet": ParagraphStyle("bullet", parent=base["BodyText"], fontSize=10,
                                  leading=13, leftIndent=16, bulletIndent=4),
    }

    story = []
    title_done = False

    for b in blocks:
        if b["type"] == "h1":
            story.append(Paragraph(render_md_inline(b["text"]), styles["h1"]))
            if score_data and not title_done:
                story.append(Spacer(1, 0.1 * inch))
                story.append(build_scorecard(score_data, styles))
                story.append(Spacer(1, 0.2 * inch))
                title_done = True
        elif b["type"] == "h2":
            story.append(Paragraph(render_md_inline(b["text"]), styles["h2"]))
        elif b["type"] == "h3":
            story.append(Paragraph(render_md_inline(b["text"]), styles["h3"]))
        elif b["type"] == "p" and b["text"]:
            story.append(Paragraph(render_md_inline(b["text"]), styles["normal"]))
        elif b["type"] == "quote":
            story.append(Paragraph(render_md_inline(b["text"]), styles["quote"]))
        elif b["type"] == "bullet":
            story.append(Paragraph("• " + render_md_inline(b["text"]),
                                   styles["bullet"]))
        elif b["type"] == "table":
            story.append(build_table(b["rows"], styles))
            story.append(Spacer(1, 0.1 * inch))
        elif b["type"] == "space":
            story.append(Spacer(1, 0.05 * inch))

    # Footer
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(
        f"<i>Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} · "
        "AI-generated estimates. Not financial or investment advice.</i>",
        styles["small"]))

    doc.build(story)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("input", help="Path to PROPERTY-ANALYSIS.md")
    p.add_argument("-o", "--output", help="Output PDF path")
    args = p.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"ERROR: {in_path} not found", file=sys.stderr)
        sys.exit(1)

    if args.output:
        out = Path(args.output)
    else:
        # Try to extract address from H1 line
        first_line = in_path.read_text().splitlines()[0] if in_path.stat().st_size else ""
        addr = first_line.replace("# Property Analysis:", "").strip() or "report"
        slug = slugify(addr)
        out = in_path.parent / f"PROPERTY-REPORT-{slug}-{datetime.now().strftime('%Y%m%d')}.pdf"

    build_pdf(in_path, out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
