#!/usr/bin/env python3
"""
Send a file (PDF report) and a message via iMessage using AppleScript.

Reads recipient from ~/.claude/re_complete_config.json:
    { "imessage_to": "+15551234567" }

If config is missing or empty, prints a helpful note and exits 0
(non-fatal — the orchestrator falls back to "PDF saved, not sent").

Refuses oversized files: iMessage's documented attachment limit is 100MB
but in practice anything past ~5MB regularly fails or stalls. Exit 4 in
that case so the orchestrator can fall back cleanly.

Usage:
    python3 send_imessage.py <pdf_path> "<message body>"

Exit codes:
    0    sent successfully (or skipped because recipient not configured)
    1    file not found / bad args
    3    osascript / Messages.app failure
    4    file too large for iMessage (>5MB)
"""
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / ".claude" / "re_complete_config.json"
DEFAULT_MAX_BYTES = 5 * 1024 * 1024   # 5 MB iMessage safe ceiling


def get_recipient() -> str | None:
    if not CONFIG_PATH.exists():
        return None
    try:
        cfg = json.loads(CONFIG_PATH.read_text())
        handle = (cfg.get("imessage_to") or "").strip()
        return handle or None
    except (json.JSONDecodeError, OSError):
        return None


def send_via_messages(recipient: str, file_path: str, body: str) -> tuple[bool, str]:
    """Drive Messages.app via AppleScript. Returns (success, output)."""
    abs_path = str(Path(file_path).resolve())

    # POSIX file path needs to be a literal string in AppleScript
    script = f'''
    tell application "Messages"
        set targetService to 1st service whose service type = iMessage
        set targetBuddy to buddy {json.dumps(recipient)} of targetService
        send {json.dumps(body)} to targetBuddy
        delay 1
        send (POSIX file {json.dumps(abs_path)}) to targetBuddy
    end tell
    '''

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return True, "sent"
        return False, (result.stderr or result.stdout or "unknown osascript error").strip()
    except FileNotFoundError:
        return False, "osascript not found (are you on macOS?)"
    except subprocess.TimeoutExpired:
        return False, "Messages.app timed out — open it manually and re-run"


def main():
    if len(sys.argv) < 2:
        print("Usage: send_imessage.py <pdf_path> [message_body]", file=sys.stderr)
        sys.exit(2)

    pdf_path = sys.argv[1]
    body = sys.argv[2] if len(sys.argv) > 2 else "Property analysis report"

    path = Path(pdf_path)
    if not path.exists():
        print(f"ERROR: file not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    size = path.stat().st_size
    max_bytes = int(os.environ.get("IMESSAGE_MAX_BYTES", DEFAULT_MAX_BYTES))
    if size > max_bytes:
        print(
            f"TOO_LARGE: {path.name} is {size / 1024 / 1024:.2f} MB which "
            f"exceeds the {max_bytes / 1024 / 1024:.0f} MB iMessage safe "
            f"ceiling. PDF saved at {path}; iMessage send skipped.",
            file=sys.stderr,
        )
        sys.exit(4)

    recipient = get_recipient()
    if not recipient:
        print(f"NOT_CONFIGURED: no iMessage recipient in {CONFIG_PATH}.")
        print("  Add one with:")
        print(f'    echo \'{{"imessage_to": "+15551234567"}}\' > {CONFIG_PATH}')
        sys.exit(0)  # Non-fatal — caller treats as "skip send"

    ok, msg = send_via_messages(recipient, pdf_path, body)
    if ok:
        print(f"SENT: to {recipient}")
        sys.exit(0)
    else:
        print(f"FAILED: {msg}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
