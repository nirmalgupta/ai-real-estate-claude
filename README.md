# AI Real Estate Analyst — Claude Code Skills

Investment-grade property analysis from a single slash command. Five parallel agents pull comps, model cash flow, score the neighborhood, run buy-and-hold / BRRRR / flip math, and read the market — then synthesize into one report and a styled PDF.

Runs entirely inside your Claude subscription (Claude Code in VS Code or terminal). **No API key, no per-token billing.**

## What you get

```
> /real-estate-analyze 1234 Oak St, Austin, TX 78701

Phase 1: Discovery...
  ✓ Listing fetched, 14 facts extracted

Phase 2: Running 5 parallel agents...
  ✓ Comparable Sales       — Fair value: $445k–$478k
  ✓ Rental & Cash Flow     — -$340/mo (negative)
  ✓ Neighborhood Quality   — 78/100
  ✓ Investment Analysis    — Only buy-and-hold pencils
  ✓ Market Conditions      — Soft seller's market

Phase 3: Synthesis...
  ✓ Composite: 64/100 — Grade B — Hold / Watch
  ✓ Wrote PROPERTY-ANALYSIS.md

> /real-estate-report-pdf
  ✓ Wrote PROPERTY-REPORT-1234-oak-st-20260509.pdf
```

## Install

```bash
git clone <your-repo-url> ai-real-estate-claude
cd ai-real-estate-claude
./install.sh
```

Then restart Claude Code.

## Commands

| Command | What it does | Output |
|---|---|---|
| `/real-estate-analyze <address>` | Full 5-agent audit + composite score | `PROPERTY-ANALYSIS.md` |
| `/real-estate-comps <address>` | Comps only — fair-market-value range | `COMPS-ANALYSIS.md` |
| `/real-estate-rental <address>` | Rent estimate + cash flow | `RENTAL-ANALYSIS.md` |
| `/real-estate-neighborhood <address>` | Schools, crime, walkability | `NEIGHBORHOOD-ANALYSIS.md` |
| `/real-estate-investment <address>` | Buy & hold / BRRRR / flip scenarios | `INVESTMENT-ANALYSIS.md` |
| `/real-estate-market <address>` | Local market conditions | `MARKET-ANALYSIS.md` |
| `/real-estate-report-pdf` | Convert latest analysis to PDF | `PROPERTY-REPORT-*.pdf` |

## Architecture

Three-phase pipeline. Phase 2 is the parallel fan-out.

```
                ┌──────────────────────┐
                │  /real-estate-analyze │
                │     (Orchestrator)    │
                └──────────┬───────────┘
                           ▼
       ┌───────────────────────────────────────┐
       │ PHASE 1 · DISCOVERY (sequential)       │
       │  • WebFetch listing                    │
       │  • analyze_property.py extracts facts  │
       │  • property_facts.json                 │
       └───────────────────┬───────────────────┘
                           ▼
       ┌───────────────────────────────────────┐
       │ PHASE 2 · 5 AGENTS (parallel via Task) │
       │  ├─ re-comps          (25%)            │
       │  ├─ re-rental         (20%)            │
       │  ├─ re-neighborhood   (20%)            │
       │  ├─ re-investment     (15%)            │
       │  └─ re-market         (20%)            │
       └───────────────────┬───────────────────┘
                           ▼
       ┌───────────────────────────────────────┐
       │ PHASE 3 · SYNTHESIS                    │
       │  • score_property.py → composite       │
       │  • Assemble PROPERTY-ANALYSIS.md       │
       │  • (Optional) PDF via reportlab        │
       └───────────────────────────────────────┘
```

## Composite scoring

Every property gets a weighted 0–100 score:

| Dimension | Weight |
|---|---|
| Comparable Value | 25% |
| Income Potential | 20% |
| Neighborhood Quality | 20% |
| Investment Upside | 15% |
| Market Conditions | 20% |

| Score | Grade | Signal |
|---|---|---|
| 90+ | A+ | Strong Buy |
| 80–89 | A | Buy |
| 70–79 | B | Hold / Watch |
| 60–69 | C | Hold / Watch |
| 50–59 | D | Caution |
| <50 | F | Avoid |

## Project structure

```
ai-real-estate-claude/
├── real-estate/SKILL.md                     # Orchestrator (routes commands)
├── skills/
│   ├── real-estate-analyze/SKILL.md         # Flagship — 5-agent fan-out
│   ├── real-estate-comps/SKILL.md           # Quick: comps only
│   ├── real-estate-rental/SKILL.md          # Quick: rent + cash flow
│   ├── real-estate-neighborhood/SKILL.md    # Quick: neighborhood
│   ├── real-estate-investment/SKILL.md      # Quick: BRRRR / flip
│   ├── real-estate-market/SKILL.md          # Quick: market conditions
│   └── real-estate-report-pdf/SKILL.md      # PDF generator
├── agents/
│   ├── re-comps.md                          # Comp analyst (subagent)
│   ├── re-rental.md                         # Rental analyst
│   ├── re-neighborhood.md                   # Neighborhood analyst
│   ├── re-investment.md                     # Investment analyst
│   └── re-market.md                         # Market analyst
├── scripts/
│   ├── analyze_property.py                  # Best-effort web scrape
│   ├── score_property.py                    # Composite calculator
│   ├── mortgage_calculator.py               # P&I / cash flow / scenarios
│   └── generate_pdf_report.py               # ReportLab PDF
├── mobile/
│   └── CLAUDE_PROJECT_INSTRUCTIONS.md       # Mobile/Claude.ai version
├── install.sh
├── uninstall.sh
├── requirements.txt                          # reportlab
└── LICENSE
```

## Mobile / phone use

The slash-command interface above only works on desktop (Claude Code in VS Code or terminal). For phone use, see `mobile/CLAUDE_PROJECT_INSTRUCTIONS.md` — paste it into a Claude Project, then chat normally on the Claude mobile app.

## Requirements

- **Claude Code** ([install](https://docs.anthropic.com/claude-code))
- **Python 3.8+** (for scripts)
- **reportlab** (for PDF — `pip install -r requirements.txt`)

## Limitations

- Web research only — no MLS, no Zillow API, no paid data feeds
- Zillow/Redfin actively block scrapers; expect occasional failures and fall back to manual address entry
- AI-generated estimates. Not financial or investment advice. Always verify with a licensed real estate professional before making decisions.

## License

MIT
