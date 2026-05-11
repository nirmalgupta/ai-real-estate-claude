"""Shared user-config loader for the install-time-opt-in setup.

`install.sh` writes ~/.claude/re_complete_config.json with this shape:
    {
      "apis": {
        "hud":          {"key": "<api key>"},
        "bea":          {"key": "<api key>"},
        "realestate":   {"key": "<api key>"}
      },
      "channels": {
        "imessage":     {"to":  "+15551234567"},
        "email":        {"to":  "...", "smtp_host": "...", "smtp_port": 587,
                          "smtp_user": "...", "smtp_password": "..."},
        "telegram":     {"bot_token": "...", "chat_id": "..."},
        "slack":        {"bot_token": "...", "channel": "C..."}
      }
    }

Every section is optional. Missing sections mean "the user declined this
service at install time" — code paths must silently skip, never prompt.

Env-var precedence: if a runtime env var is set (e.g. `HUD_API_KEY`), it
wins over the config file value. That keeps CI / scripted use trivial.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_PATH = Path.home() / ".claude" / "re_complete_config.json"


def load() -> dict:
    """Return the parsed config, or `{}` if missing/unparseable."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def api_key(name: str, env_var: str | None = None) -> str | None:
    """Pick the best available value for an API key.

    Order:
      1. The named env var (if provided and set)
      2. The named env var derived from `name` if it's an obvious match
      3. `apis.<name>.key` in the config file

    Returns None if no key is configured.
    """
    if env_var:
        v = os.environ.get(env_var)
        if v:
            return v
    derived = f"{name.upper()}_API_KEY"
    if (env_var or "") != derived:
        v = os.environ.get(derived)
        if v:
            return v
    cfg = load()
    apis = (cfg.get("apis") or {})
    sub = apis.get(name) or {}
    key = sub.get("key")
    return key.strip() if isinstance(key, str) and key.strip() else None
