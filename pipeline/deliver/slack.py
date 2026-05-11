"""Slack delivery via files.upload v2.

Config block shape:
    "slack": {
        "bot_token": "xoxb-...",       (required for file upload)
        "channel": "C0123456789"       (channel ID; not the #name)
    }

Slack deprecated `files.upload` in 2024 and replaced it with a two-step
`files.getUploadURLExternal` → `files.completeUploadExternal` flow. We
implement the new flow here so this channel keeps working.

The required scope on the bot is `files:write`. Channel ID (not name)
is the safest target — names can be ambiguous between user channels and
private channels.
"""
from __future__ import annotations

from pathlib import Path

import httpx

from pipeline.deliver import Channel, SendResult

_SLACK_API = "https://slack.com/api"
# Slack's per-file ceiling is 5 GB but the upload URL flow times out for
# huge uploads; our PDFs stay well under 25 MB which is more than fine.
_SLACK_MAX_BYTES = 25 * 1024 * 1024


class SlackChannel(Channel):
    name = "slack"
    max_bytes = _SLACK_MAX_BYTES

    def is_configured(self, config: dict) -> bool:
        return bool(
            (config.get("bot_token") or "").strip()
            and (config.get("channel") or "").strip()
        )

    def send(self, pdf_path: Path, body: str, config: dict) -> SendResult:
        token = config["bot_token"].strip()
        channel = config["channel"].strip()
        headers = {"Authorization": f"Bearer {token}"}

        size = pdf_path.stat().st_size

        # Step 1: get an upload URL
        try:
            r1 = httpx.get(
                f"{_SLACK_API}/files.getUploadURLExternal",
                headers=headers,
                params={"filename": pdf_path.name, "length": str(size)},
                timeout=30.0,
            )
            r1.raise_for_status()
            p1 = r1.json()
        except (httpx.HTTPError, ValueError) as e:
            return SendResult(ok=False, note=f"Slack upload-url request failed: {e}")
        if not p1.get("ok"):
            return SendResult(
                ok=False,
                note=f"Slack getUploadURLExternal error: {p1.get('error')}",
            )

        upload_url = p1["upload_url"]
        file_id = p1["file_id"]

        # Step 2: upload bytes to that URL
        try:
            with pdf_path.open("rb") as fh:
                r2 = httpx.post(upload_url, content=fh.read(), timeout=120.0)
        except (httpx.HTTPError, OSError) as e:
            return SendResult(ok=False, note=f"Slack file upload failed: {e}")
        if r2.status_code != 200:
            return SendResult(
                ok=False,
                note=f"Slack upload HTTP {r2.status_code}: {r2.text[:160]}",
            )

        # Step 3: complete + share to channel
        try:
            r3 = httpx.post(
                f"{_SLACK_API}/files.completeUploadExternal",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "files": [{"id": file_id, "title": pdf_path.name}],
                    "channel_id": channel,
                    "initial_comment": body or "",
                },
                timeout=30.0,
            )
            r3.raise_for_status()
            p3 = r3.json()
        except (httpx.HTTPError, ValueError) as e:
            return SendResult(ok=False, note=f"Slack complete-upload failed: {e}")
        if not p3.get("ok"):
            return SendResult(
                ok=False,
                note=f"Slack completeUploadExternal error: {p3.get('error')}",
            )

        return SendResult(ok=True, note=f"sent to channel {channel}")
