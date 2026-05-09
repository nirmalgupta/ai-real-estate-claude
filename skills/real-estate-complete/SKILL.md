---
name: real-estate-complete
description: One-shot pipeline. Runs full property analysis, generates PDF, then sends the PDF to the user's iMessage. Trigger on /real-estate-complete or "analyze this property and text it to me", "send the property report to my phone".
---

# Real Estate — Complete Pipeline

End-to-end: analyze → PDF → iMessage. One command, one outcome.

## Steps

### 1. Run the full analysis

Invoke the `real-estate-analyze` skill with the user's address. This produces:
- `PROPERTY-ANALYSIS.md` — the full report
- `composite_score.json` — for the PDF scorecard

Wait for it to complete fully before continuing.

### 2. Generate the PDF

Run:
```
python3 ~/.claude/scripts/generate_pdf_report.py PROPERTY-ANALYSIS.md
```

The script writes `PROPERTY-REPORT-<address-slug>-<YYYYMMDD>.pdf` in the cwd. Capture the exact filename it printed.

If the command fails because `reportlab` isn't installed, tell the user to run:
```
pip3 install --break-system-packages reportlab
```
…then stop. Don't continue to step 3 without a PDF.

### 3. Send via iMessage

Compose a one-line summary message (address + score + verdict). Then run:

```
python3 ~/.claude/scripts/send_imessage.py "<pdf_path>" "<summary message>"
```

Example summary:
> "26 Glenleigh Pl: 64/100 (Hold). PDF attached."

Possible outcomes from the script:
- **`SENT: to <handle>`** → tell the user it was sent, where, and the score headline.
- **`NOT_CONFIGURED: ...`** → tell the user the PDF was generated but no iMessage recipient is configured. Show them the exact `echo` command the script printed to set one. The PDF is still on disk and they can open it directly.
- **`FAILED: <error>`** → report the error verbatim. Likely causes: Messages.app not signed in, recipient handle wrong, macOS permission dialog blocking automation. Tell the user to open Messages.app manually and check.

### 4. Final summary

Tell the user:
- File path to the PDF
- Whether iMessage send succeeded
- The headline score + grade + signal
- Single-line action recommendation

## Notes

- **Recipient is per-user.** The handle lives in `~/.claude/re_complete_config.json`, never in the repo. Different users on different machines send to their own phones.
- **No fallback.** If the user has no recipient configured, do NOT try to send to any default — leave the PDF on disk and inform them.
- **Permissions on macOS.** First time Messages.app receives an automation request, macOS shows a security dialog. The send will fail until the user clicks "OK" — tell them to expect this on first run.
