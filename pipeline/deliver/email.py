"""Email delivery via stdlib SMTP.

Config block shape:
    "email": {
        "to": "you@example.com",
        "from": "reports@example.com",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_user": "you@gmail.com",
        "smtp_password": "<app-specific password>",
        "use_tls": true            (default true)
    }

Uses only Python stdlib — no extra dependencies. The recipient is the
"to" field; "from" defaults to "smtp_user" if not set.

For Gmail you'll need an App Password (not your account password) —
Google requires this for SMTP since 2022.
"""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from pipeline.deliver import Channel, SendResult

# Email attachment limits are typically far more generous than iMessage
# (Gmail 25 MB, most others ≥10 MB). Keep our cap at 20 MB to stay under
# every well-known limit including older Exchange policies.
_DEFAULT_MAX_BYTES = 20 * 1024 * 1024


class EmailChannel(Channel):
    name = "email"
    max_bytes = _DEFAULT_MAX_BYTES

    REQUIRED = ("to", "smtp_host", "smtp_port", "smtp_user", "smtp_password")

    def is_configured(self, config: dict) -> bool:
        return all((config.get(k) or "") for k in self.REQUIRED)

    def send(self, pdf_path: Path, body: str, config: dict) -> SendResult:
        msg = EmailMessage()
        msg["Subject"] = body.splitlines()[0] if body else "Property analysis"
        msg["From"] = config.get("from") or config["smtp_user"]
        msg["To"] = config["to"]
        msg.set_content(body or "Property analysis report attached.")

        try:
            data = pdf_path.read_bytes()
        except OSError as e:
            return SendResult(ok=False, note=f"failed to read PDF: {e}")
        msg.add_attachment(data, maintype="application", subtype="pdf",
                           filename=pdf_path.name)

        host = config["smtp_host"]
        port = int(config["smtp_port"])
        use_tls = config.get("use_tls", True)

        try:
            ctx = ssl.create_default_context()
            if port == 465:
                # SMTPS (implicit TLS)
                with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as smtp:
                    smtp.login(config["smtp_user"], config["smtp_password"])
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=30) as smtp:
                    smtp.ehlo()
                    if use_tls:
                        smtp.starttls(context=ctx)
                        smtp.ehlo()
                    smtp.login(config["smtp_user"], config["smtp_password"])
                    smtp.send_message(msg)
        except smtplib.SMTPException as e:
            return SendResult(ok=False, note=f"SMTP error: {e}")
        except OSError as e:
            return SendResult(ok=False, note=f"SMTP connection error: {e}")

        return SendResult(ok=True, note=f"sent to {config['to']}")
