"""
Outgoing email, behind one function. Provider is chosen with EMAIL_PROVIDER:

    console  log the message instead of sending it (default — dev/CI)
    resend   Resend's HTTP API              (RESEND_API_KEY)
    smtp     any SMTP server — Brevo, Amazon SES, Gmail app password…
             (SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD; STARTTLS on
             587 by default, SMTP_USE_TLS=false for implicit TLS on 465)

`send_email` raises on failure; the outbox worker
(core/notification_worker.py) catches that and retries with backoff.
"""
import asyncio
import logging
import smtplib
from email.message import EmailMessage

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailError(Exception):
    pass


def _clean_header(value: str) -> str:
    # Stop header injection: a header value must never contain a line break.
    return " ".join(value.replace("\r", " ").replace("\n", " ").split())


async def send_email(to: str, subject: str, text: str, html: str | None = None) -> None:
    to = _clean_header(to)
    subject = _clean_header(subject)
    provider = settings.email_provider.lower()

    if provider == "console":
        logger.info("EMAIL (console provider, not sent) to=%s subject=%s\n%s", to, subject, text)
        return
    if provider == "resend":
        await _send_resend(to, subject, text, html)
        return
    if provider == "smtp":
        await asyncio.to_thread(_send_smtp, to, subject, text, html)
        return
    raise EmailError(f"Unknown EMAIL_PROVIDER {settings.email_provider!r} (use console, resend or smtp)")


async def _send_resend(to: str, subject: str, text: str, html: str | None) -> None:
    if not settings.resend_api_key:
        raise EmailError("EMAIL_PROVIDER=resend but RESEND_API_KEY is empty")
    payload = {"from": settings.email_from, "to": [to], "subject": subject, "text": text}
    if html:
        payload["html"] = html
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            json=payload,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        )
    if resp.status_code >= 400:
        # Resend's error body explains e.g. an unverified sender domain.
        raise EmailError(f"Resend responded {resp.status_code}: {resp.text[:300]}")


def _send_smtp(to: str, subject: str, text: str, html: str | None) -> None:
    if not settings.smtp_host:
        raise EmailError("EMAIL_PROVIDER=smtp but SMTP_HOST is empty")
    msg = EmailMessage()
    msg["From"] = _clean_header(settings.email_from)
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    if settings.smtp_use_tls:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
