"""Multi-channel report delivery.

A Channel is a plug-in that takes a PDF path + a body message and pushes
the artifact somewhere — iMessage, email, Telegram, Slack. Each channel
is self-contained (its own credentials, its own send call); this module
just registers them and dispatches by name.

Configuration lives in ~/.claude/re_complete_config.json:
    {
      "channels": {
        "imessage": {"to": "+15551234567"},
        "email":    {"to": "you@example.com", "smtp_user": "...", ...},
        "telegram": {"chat_id": "123456", "bot_token": "..."},
        "slack":    {"webhook_url": "..."}
      }
    }

A channel is "enabled" iff its config block exists and is non-empty. The
end-to-end flow stays graceful: if no channels are configured, the PDF
is saved to disk and the orchestrator continues (per the open-source
philosophy: free path works, paid path opt-in).
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path.home() / ".claude" / "re_complete_config.json"
DEFAULT_MAX_BYTES = 5 * 1024 * 1024


@dataclass
class SendResult:
    """What a Channel.send() returns."""
    ok: bool
    note: str   # human-readable status (sent / not configured / failed: …)
    skipped: bool = False   # True if channel wasn't configured (non-error)


class Channel(ABC):
    """Base class for every delivery channel."""
    name: str = "unnamed"
    max_bytes: int = DEFAULT_MAX_BYTES

    @abstractmethod
    def is_configured(self, config: dict) -> bool:
        """Return True if this channel has enough config to attempt a send."""

    @abstractmethod
    def send(self, pdf_path: Path, body: str, config: dict) -> SendResult:
        """Push the PDF + body. Caller has already validated existence + size."""


_REGISTRY: dict[str, Channel] = {}


def register(channel: Channel) -> None:
    _REGISTRY[channel.name] = channel


def channels() -> dict[str, Channel]:
    return dict(_REGISTRY)


def load_config() -> dict:
    """Load the shared delivery config blob. Empty dict if missing/broken."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def enabled_channels(config: dict | None = None) -> list[str]:
    """Return the names of channels whose config is filled in."""
    cfg = config if config is not None else load_config()
    channel_cfg = cfg.get("channels", {}) or {}
    enabled = []
    for name, ch in _REGISTRY.items():
        sub_cfg = channel_cfg.get(name, {}) or {}
        if ch.is_configured(sub_cfg):
            enabled.append(name)
    return enabled


def send(channel_name: str, pdf_path: Path, body: str,
         config: dict | None = None) -> SendResult:
    """Send via one channel by name.

    Returns SendResult — never raises for "expected" failures (missing
    config, oversized, channel not registered). Raises only for unforeseen
    exceptions inside a channel implementation, so callers can log + skip.
    """
    if channel_name not in _REGISTRY:
        return SendResult(ok=False, note=f"unknown channel: {channel_name}")
    if not pdf_path.exists():
        return SendResult(ok=False, note=f"file not found: {pdf_path}")

    cfg = config if config is not None else load_config()
    channel_cfg = (cfg.get("channels", {}) or {}).get(channel_name, {}) or {}
    ch = _REGISTRY[channel_name]
    if not ch.is_configured(channel_cfg):
        return SendResult(ok=False, note=f"{channel_name} not configured",
                          skipped=True)

    size = pdf_path.stat().st_size
    if size > ch.max_bytes:
        return SendResult(
            ok=False,
            note=(f"file too large: {size / 1024 / 1024:.2f} MB > "
                  f"{ch.max_bytes / 1024 / 1024:.0f} MB {channel_name} ceiling"),
        )

    return ch.send(pdf_path, body, channel_cfg)


# Register channels on import. Each channel module guards heavy imports
# behind its own send() so we don't pay the cost for channels the user
# isn't using.
from pipeline.deliver.email import EmailChannel  # noqa: E402
from pipeline.deliver.imessage import ImessageChannel  # noqa: E402

register(ImessageChannel())
register(EmailChannel())
