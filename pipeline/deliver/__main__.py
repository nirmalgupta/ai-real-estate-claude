"""CLI driver for the multi-channel delivery layer.

Usage:
  python3 -m pipeline.deliver --list
      Print which channels are enabled (configured) right now.

  python3 -m pipeline.deliver --pdf <path> --body "<msg>" [--to imessage,email,...]
      Send the PDF to one or more enabled channels. With no --to, sends
      to every enabled channel. Prints per-channel success/failure.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline.deliver import (
    channels as _channels,
    enabled_channels,
    send_to_many,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Send a PDF report via configured channels.")
    p.add_argument("--list", action="store_true",
                   help="Print enabled channels and exit.")
    p.add_argument("--pdf", type=Path, help="PDF file to send.")
    p.add_argument("--body", default="Property analysis report",
                   help="Message body / caption.")
    p.add_argument("--to",
                   help="Comma-separated channel names. Default: all enabled.")
    args = p.parse_args(argv)

    enabled = enabled_channels()
    known = list(_channels().keys())

    if args.list or not args.pdf:
        if args.list:
            if enabled:
                print("Enabled channels: " + ", ".join(enabled))
            else:
                print("No channels configured. Re-run install.sh to set some up.")
            print("Known channels: " + ", ".join(known))
            return 0
        print("ERROR: --pdf <path> required (or --list).", file=sys.stderr)
        return 2

    if not args.pdf.exists():
        print(f"ERROR: file not found: {args.pdf}", file=sys.stderr)
        return 1

    if args.to:
        names = [n.strip() for n in args.to.split(",") if n.strip()]
        unknown = [n for n in names if n not in known]
        if unknown:
            print(f"ERROR: unknown channel(s): {', '.join(unknown)}. "
                  f"Known: {', '.join(known)}", file=sys.stderr)
            return 2
    else:
        names = enabled
        if not names:
            print("No channels enabled — nothing to do. PDF saved at:",
                  args.pdf)
            return 0

    results = send_to_many(names, args.pdf, args.body)
    any_failed = False
    for name, r in results.items():
        marker = "ok " if r.ok else ("skip" if r.skipped else "FAIL")
        print(f"  [{marker}] {name}: {r.note}")
        if not r.ok and not r.skipped:
            any_failed = True

    return 0 if not any_failed else 3


if __name__ == "__main__":
    sys.exit(main())
