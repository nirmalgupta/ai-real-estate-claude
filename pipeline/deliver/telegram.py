"""Telegram delivery via Bot API.

Config block shape:
    "telegram": {
        "bot_token": "<numeric>:<rest>",
        "chat_id":   "123456789"
    }

Setup:
  1. Talk to @BotFather on Telegram, /newbot, copy the token.
  2. Start a chat with your new bot, send any message.
  3. Hit https://api.telegram.org/bot<token>/getUpdates and read the
     `chat.id` field from the most recent message.

Uses the Bot API's sendDocument endpoint, which has a 50 MB ceiling for
HTTP uploads — plenty for our PDFs.
"""
from __future__ import annotations

from pathlib import Path

import httpx

from pipeline.deliver import Channel, SendResult

# Telegram Bot API caps HTTP uploads at 50 MB; ours stay well under that.
_TG_MAX_BYTES = 50 * 1024 * 1024
_API_BASE = "https://api.telegram.org"


class TelegramChannel(Channel):
    name = "telegram"
    max_bytes = _TG_MAX_BYTES

    def is_configured(self, config: dict) -> bool:
        return bool(
            (config.get("bot_token") or "").strip()
            and (config.get("chat_id") or "").strip()
        )

    def send(self, pdf_path: Path, body: str, config: dict) -> SendResult:
        token = config["bot_token"].strip()
        chat_id = str(config["chat_id"]).strip()

        url = f"{_API_BASE}/bot{token}/sendDocument"
        try:
            with pdf_path.open("rb") as fh:
                files = {"document": (pdf_path.name, fh, "application/pdf")}
                data = {"chat_id": chat_id, "caption": body or ""}
                r = httpx.post(url, data=data, files=files, timeout=60.0)
        except (httpx.HTTPError, OSError) as e:
            return SendResult(ok=False, note=f"Telegram request failed: {e}")

        if r.status_code != 200:
            return SendResult(
                ok=False,
                note=f"Telegram HTTP {r.status_code}: {r.text[:160]}",
            )
        try:
            payload = r.json()
        except ValueError:
            return SendResult(ok=False, note="Telegram returned non-JSON")
        if not payload.get("ok"):
            return SendResult(
                ok=False,
                note=f"Telegram API error: {payload.get('description', 'unknown')}",
            )
        return SendResult(ok=True, note=f"sent to chat_id {chat_id}")
