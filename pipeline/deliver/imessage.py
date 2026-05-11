"""iMessage delivery via Messages.app + AppleScript (macOS only).

Config block shape:
    "imessage": { "to": "+15551234567" }

Either a phone number (E.164) or an email-Apple-ID handle is accepted —
whatever Messages.app already knows how to deliver to.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pipeline.deliver import Channel, SendResult


class ImessageChannel(Channel):
    name = "imessage"
    # iMessage's documented attachment cap is 100 MB but in practice
    # anything past 5 MB regularly fails or stalls. Conservative ceiling.
    max_bytes = 5 * 1024 * 1024

    def is_configured(self, config: dict) -> bool:
        return bool((config.get("to") or "").strip())

    def send(self, pdf_path: Path, body: str, config: dict) -> SendResult:
        recipient = config["to"].strip()
        abs_path = str(pdf_path.resolve())

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
        except FileNotFoundError:
            return SendResult(ok=False,
                              note="osascript not found (macOS only)")
        except subprocess.TimeoutExpired:
            return SendResult(ok=False,
                              note="Messages.app timed out — open it manually")

        if result.returncode == 0:
            return SendResult(ok=True, note=f"sent to {recipient}")
        err = (result.stderr or result.stdout or "unknown osascript error").strip()
        return SendResult(ok=False, note=f"osascript failed: {err}")
