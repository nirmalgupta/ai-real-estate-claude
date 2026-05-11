#!/usr/bin/env python3
"""Interactive setup for ~/.claude/re_complete_config.json.

Called by install.sh after the file-copy phase. Loops over every
optional API key and delivery channel, asks the user once at setup
time, and saves the result. Re-entrant: already-configured entries are
preserved unless `--reset` is passed.

Per the project's open-source / hobby philosophy: anything you skip
here is silently skipped at runtime forever — no mid-use prompts.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Callable

CONFIG_PATH = Path.home() / ".claude" / "re_complete_config.json"


# --- IO helpers --------------------------------------------------------

def _prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        v = input(f"  {text}{suffix}: ").strip()
    except EOFError:
        return default
    return v or default


def _yes_no(text: str, default: bool = False) -> bool:
    d = "y/N" if not default else "Y/n"
    while True:
        try:
            v = input(f"  {text} ({d}): ").strip().lower()
        except EOFError:
            return default
        if not v:
            return default
        if v in ("y", "yes"):
            return True
        if v in ("n", "no"):
            return False
        print("    please answer y or n")


def _section(title: str) -> None:
    print()
    print(f"  {title}")
    print(f"  {'-' * len(title)}")


# --- Schema -------------------------------------------------------------


class Item:
    """One prompt-able config item — an API or a channel."""

    def __init__(self, section: str, key: str, label: str,
                 explainer: str, signup_url: str | None,
                 prompt: Callable[[dict], dict]):
        self.section = section          # 'apis' or 'channels'
        self.key = key                  # 'hud', 'imessage', etc.
        self.label = label              # display name
        self.explainer = explainer      # one-line context
        self.signup_url = signup_url    # link the user might follow
        self.prompt = prompt            # callable returning the saved subdict


# Per-channel prompters return the dict that goes under
# `channels.<name>` (or None to skip).

def _prompt_imessage(existing: dict) -> dict | None:
    cur = (existing or {}).get("to") or ""
    print("  Phone number (e.g. +15551234567) or Apple ID email, or blank to skip.")
    to = _prompt("iMessage handle", default=cur)
    return {"to": to} if to else None


def _prompt_email(existing: dict) -> dict | None:
    print("  SMTP delivery via Gmail / your own server.")
    print("  For Gmail you need an App Password (myaccount.google.com → Security).")
    e = existing or {}
    to = _prompt("recipient email", default=e.get("to", ""))
    if not to:
        return None
    smtp_host = _prompt("SMTP host", default=e.get("smtp_host", "smtp.gmail.com"))
    smtp_port = _prompt("SMTP port", default=str(e.get("smtp_port", 587)))
    smtp_user = _prompt("SMTP user", default=e.get("smtp_user", ""))
    smtp_password = _prompt(
        "SMTP password (App Password, hidden in saved file)",
        default=e.get("smtp_password", ""),
    )
    if not (smtp_user and smtp_password):
        print("    skipped — incomplete credentials")
        return None
    return {
        "to": to, "from": e.get("from") or smtp_user,
        "smtp_host": smtp_host, "smtp_port": int(smtp_port),
        "smtp_user": smtp_user, "smtp_password": smtp_password,
    }


def _prompt_telegram(existing: dict) -> dict | None:
    print("  Talk to @BotFather, /newbot, copy the token. Then send your bot a")
    print("  message and hit api.telegram.org/bot<token>/getUpdates to find chat_id.")
    e = existing or {}
    bot_token = _prompt("bot token", default=e.get("bot_token", ""))
    chat_id = _prompt("chat_id", default=str(e.get("chat_id", "")))
    if not (bot_token and chat_id):
        return None
    return {"bot_token": bot_token, "chat_id": chat_id}


def _prompt_slack(existing: dict) -> dict | None:
    print("  Slack bot with `files:write` scope. Channel ID (not name).")
    e = existing or {}
    bot_token = _prompt("bot token (xoxb-…)", default=e.get("bot_token", ""))
    channel = _prompt("channel ID (C…)", default=e.get("channel", ""))
    if not (bot_token and channel):
        return None
    return {"bot_token": bot_token, "channel": channel}


def _prompt_api_key(name: str, signup_url: str) -> Callable[[dict], dict | None]:
    """Build a one-line "paste your API key" prompter for an API."""
    def _inner(existing: dict) -> dict | None:
        cur = (existing or {}).get("key", "")
        if cur:
            print(f"  Already configured (length {len(cur)} chars).")
            if not _yes_no("Replace it?", default=False):
                return {"key": cur}
        print(f"  Get a free key at {signup_url}")
        v = _prompt(f"{name} API key (or blank to skip)")
        return {"key": v} if v else None
    return _inner


ITEMS: list[Item] = [
    Item("apis", "hud", "HUD Fair Market Rent",
         "Bedroom-matched rent benchmarks for cap-rate / GRM calcs.",
         "https://www.huduser.gov/hudapi/",
         _prompt_api_key("HUD", "https://www.huduser.gov/hudapi/")),
    Item("apis", "bea", "BEA Regional",
         "County per-capita personal income (a stronger neighborhood tier signal than ACS).",
         "https://apps.bea.gov/api/signup/",
         _prompt_api_key("BEA", "https://apps.bea.gov/api/signup/")),
    Item("apis", "realestate", "RealEstateAPI (paid)",
         "Paid CAD-data fallback for counties we don't yet support — Tarrant TX, Harris TX, Durham NC, Chatham NC. Skip if you don't pay for it.",
         "https://developer.realestateapi.com/",
         _prompt_api_key("RealEstateAPI", "https://developer.realestateapi.com/")),
    Item("channels", "imessage", "iMessage", "macOS-only.", None, _prompt_imessage),
    Item("channels", "email", "Email/SMTP", "Any provider; Gmail needs an App Password.", None, _prompt_email),
    Item("channels", "telegram", "Telegram", "Bot API. Free, no quotas.", None, _prompt_telegram),
    Item("channels", "slack", "Slack", "Files via Bot API; needs files:write scope.", None, _prompt_slack),
]


# --- Driver -------------------------------------------------------------

def _load() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        pass


def _migrate(cfg: dict) -> dict:
    """Legacy single-key shape → new nested shape."""
    legacy = (cfg.get("imessage_to") or "").strip()
    if legacy:
        cfg.setdefault("channels", {}).setdefault("imessage", {}).setdefault("to", legacy)
        cfg.pop("imessage_to", None)
    return cfg


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--reset", action="store_true",
                   help="Re-prompt every item even if already configured.")
    args = p.parse_args(argv)

    cfg = _migrate(_load())

    print()
    print("  Optional services — configure once at install time, never prompted at runtime.")
    print("  Press Enter to skip any item; you can re-run install.sh later to add more.")

    # APIs first, then channels — order matches the user's mental model
    cur_section = None
    for item in ITEMS:
        if item.section != cur_section:
            _section("API keys" if item.section == "apis" else "Delivery channels")
            cur_section = item.section

        sub = cfg.setdefault(item.section, {})
        existing = sub.get(item.key) or {}
        configured = bool(existing)

        if configured and not args.reset:
            print(f"  • {item.label}: already configured.")
            continue

        print(f"  • {item.label} — {item.explainer}")
        new_val = item.prompt(existing)
        if new_val:
            sub[item.key] = new_val
            print("    saved.")
        else:
            sub.pop(item.key, None)
            print("    skipped.")

    _save(cfg)
    print()
    print(f"  Wrote {CONFIG_PATH}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
