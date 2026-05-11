#!/usr/bin/env python3
"""
Send a PDF via iMessage.

This script is now a thin wrapper around `pipeline.deliver` — kept so
that existing orchestration scripts that shell out to it keep working.
For new code prefer `pipeline.deliver.send("imessage", path, body)`
directly.

Reads recipient from ~/.claude/re_complete_config.json. The legacy shape
({"imessage_to": "+...."}) is still supported transparently; the new
shape is {"channels": {"imessage": {"to": "+...."}}}.

Usage:
    python3 send_imessage.py <pdf_path> [message body]

Exit codes:
    0    sent / skipped (no recipient configured)
    1    file not found
    3    Messages.app or AppleScript failure
    4    file too large for iMessage (>5 MB)
"""
import sys
from pathlib import Path

from pipeline.deliver import CONFIG_PATH, load_config, send


def _migrate_legacy(cfg: dict) -> dict:
    """If the old top-level {imessage_to:...} shape is present, lift it
    into channels.imessage.to so the registry sees it."""
    legacy = (cfg.get("imessage_to") or "").strip()
    if not legacy:
        return cfg
    ch = cfg.setdefault("channels", {})
    ch.setdefault("imessage", {}).setdefault("to", legacy)
    return cfg


def main():
    if len(sys.argv) < 2:
        print("Usage: send_imessage.py <pdf_path> [message_body]",
              file=sys.stderr)
        sys.exit(2)

    pdf_path = Path(sys.argv[1])
    body = sys.argv[2] if len(sys.argv) > 2 else "Property analysis report"

    if not pdf_path.exists():
        print(f"ERROR: file not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    cfg = _migrate_legacy(load_config())
    result = send("imessage", pdf_path, body, config=cfg)

    if result.skipped:
        print(f"NOT_CONFIGURED: no iMessage recipient in {CONFIG_PATH}.")
        print(
            "  Add one with:\n"
            f"    echo '{{\"channels\": {{\"imessage\": {{\"to\": "
            "\"+15551234567\"}}}}}' > " + str(CONFIG_PATH)
        )
        sys.exit(0)

    if result.ok:
        print(f"SENT: {result.note}")
        sys.exit(0)

    if "too large" in result.note:
        print(f"TOO_LARGE: {result.note}", file=sys.stderr)
        sys.exit(4)

    print(f"FAILED: {result.note}", file=sys.stderr)
    sys.exit(3)


if __name__ == "__main__":
    main()
