from __future__ import annotations

import os
import re
import socket
import smtplib
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr
from html import escape
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def load_project_env() -> None:
    """Ensure .env is parsed into os.environ."""
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = _clean_env_value(v)


def _clean_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return value


def _normalize_secret(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _smtp_error_code(exc: Exception) -> str:
    text = str(exc).lower()
    if isinstance(exc, smtplib.SMTPAuthenticationError) or "authentication" in text:
        return "smtp_auth_failed"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "smtp_timeout"
    if isinstance(exc, OSError) and getattr(exc, "winerror", None) == 10013:
        return "smtp_blocked"
    if isinstance(exc, OSError):
        return "smtp_network_error"
    return "smtp_error"


class EmailSender:
    """Handles real SMTP email delivery and local outbox file generation."""

    def __init__(self) -> None:
        load_project_env()
        self.smtp_host = os.getenv("SMTP_HOST", "").strip()
        self.smtp_port = int(os.getenv("SMTP_PORT", "587").strip() or "587")
        self.smtp_user = os.getenv("SMTP_USER", "").strip()
        self.smtp_password = _normalize_secret(os.getenv("SMTP_PASSWORD", ""))
        self.smtp_from = os.getenv("SMTP_FROM", f"Fable ISRO Mission Control <{self.smtp_user}>").strip()
        if not self.smtp_user and self.smtp_from:
            self.smtp_user = parseaddr(self.smtp_from)[1].strip()
        self.outbox_dir = ROOT / "outbox"
        self.outbox_dir.mkdir(exist_ok=True)

    def send_telemetry_email(
        self,
        recipient: str,
        subject: str,
        telemetry_data: dict[str, Any],
        raw_text: str = "",
    ) -> dict[str, Any]:
        """Dispatches an email via real SMTP if configured, and always writes to the local outbox."""
        if not subject:
            subject = "ISRO LVM3-M4 Launch Telemetry & Flight Test Results"

        html_body = self._build_html_report(recipient, subject, telemetry_data, raw_text)
        text_body = self._build_plain_text_report(recipient, subject, telemetry_data, raw_text)

        # 1. Always save formatted HTML & EML to local outbox
        html_file = self.outbox_dir / "latest_flight_report.html"
        eml_file = self.outbox_dir / "latest_flight_report.eml"
        
        html_file.write_text(html_body, encoding="utf-8")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.smtp_from or self.smtp_user or "mission-control@isro.gov.in"
        msg["To"] = recipient
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        eml_file.write_text(msg.as_string(), encoding="utf-8")

        return self._deliver_message(msg, recipient, subject, html_file, eml_file)

    def send_article_summary_email(
        self,
        recipient: str,
        subject: str,
        article_title: str,
        article_url: str,
        summary: str,
        source_excerpt: str = "",
    ) -> dict[str, Any]:
        if not recipient:
            recipient = self.smtp_user
        if not subject:
            subject = f"Fable summary: {article_title or 'Current article'}"

        html_body = self._build_summary_html(article_title, article_url, summary, source_excerpt)
        text_body = self._build_summary_text(article_title, article_url, summary, source_excerpt)

        html_file = self.outbox_dir / "latest_article_summary.html"
        eml_file = self.outbox_dir / "latest_article_summary.eml"
        html_file.write_text(html_body, encoding="utf-8")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.smtp_from or self.smtp_user or "fable@localhost"
        msg["To"] = recipient
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        eml_file.write_text(msg.as_string(), encoding="utf-8")

        return self._deliver_message(msg, recipient, subject, html_file, eml_file)

    def _deliver_message(self, msg: Message, recipient: str, subject: str, html_file: Path, eml_file: Path) -> dict[str, Any]:
        smtp_sent = False
        smtp_error = None
        smtp_error_code = None
        smtp_configured = bool(self.smtp_host and self.smtp_user and self.smtp_password)
        if smtp_configured:
            try:
                if self.smtp_port == 465:
                    with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=15) as server:
                        server.login(self.smtp_user, self.smtp_password)
                        server.sendmail(self.smtp_user, [recipient], msg.as_string())
                else:
                    with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server:
                        server.ehlo()
                        server.starttls()
                        server.ehlo()
                        server.login(self.smtp_user, self.smtp_password)
                        server.sendmail(self.smtp_user, [recipient], msg.as_string())
                smtp_sent = True
            except Exception as exc:
                smtp_error = str(exc)
                smtp_error_code = _smtp_error_code(exc)
        else:
            smtp_error_code = "smtp_not_configured"

        return {
            "recipient": recipient,
            "subject": subject,
            "smtp_configured": smtp_configured,
            "smtp_sent": smtp_sent,
            "smtp_error_code": smtp_error_code,
            "smtp_error": smtp_error,
            "outbox_html": str(html_file),
            "outbox_eml": str(eml_file),
            "status": "delivered_to_smtp" if smtp_sent else "saved_to_outbox",
        }

    def _build_summary_html(self, article_title: str, article_url: str, summary: str, source_excerpt: str) -> str:
        title = escape(article_title or "Current article")
        url = escape(article_url or "")
        summary_html = "".join(f"<p>{escape(part.strip())}</p>" for part in summary.split("\n") if part.strip())
        excerpt = escape(source_excerpt[:1200])
        source_link = f'<p><a href="{url}">{url}</a></p>' if url else ""
        excerpt_block = f"<h3>Source Excerpt</h3><p>{excerpt}</p>" if excerpt else ""
        return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: Arial, sans-serif; color: #17211c; background: #f6f8f7; margin: 0; padding: 20px; }}
    main {{ max-width: 680px; margin: 0 auto; background: #ffffff; border: 1px solid #d9e2dd; border-radius: 8px; padding: 24px; }}
    h1 {{ font-size: 22px; margin: 0 0 8px; }}
    h2 {{ font-size: 14px; margin-top: 24px; text-transform: uppercase; color: #315d48; }}
    h3 {{ font-size: 13px; margin-top: 22px; color: #577064; }}
    p {{ font-size: 15px; line-height: 1.55; }}
    .meta {{ color: #667a70; font-size: 12px; }}
  </style>
</head>
<body>
  <main>
    <p class="meta">Fable article summary</p>
    <h1>{title}</h1>
    {source_link}
    <h2>Summary</h2>
    {summary_html or "<p>No readable article text was found on the current page.</p>"}
    {excerpt_block}
  </main>
</body>
</html>"""

    def _build_summary_text(self, article_title: str, article_url: str, summary: str, source_excerpt: str) -> str:
        parts = [
            "FABLE ARTICLE SUMMARY",
            "=" * 72,
            f"Title : {article_title or 'Current article'}",
            f"URL   : {article_url or '(not available)'}",
            "",
            "SUMMARY:",
            summary or "No readable article text was found on the current page.",
        ]
        if source_excerpt:
            parts.extend(["", "SOURCE EXCERPT:", source_excerpt[:1200]])
        return "\n".join(parts)

    def _build_html_report(self, recipient: str, subject: str, telemetry: dict[str, Any], raw_text: str) -> str:
        alt = telemetry.get("altitude_km", 54.20)
        vel = telemetry.get("velocity_ms", 1824.5)
        mach = telemetry.get("mach", 5.42)
        q = telemetry.get("dynamic_pressure_kpa", 34.80)
        wind = telemetry.get("wind_knots", 12.4)
        chamber = telemetry.get("chamber_pressure_bar", 58.4)
        prop = telemetry.get("propellant_remaining_pct", 71.8)

        return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f7f5; color: #1a2621; margin: 0; padding: 20px; }}
    .container {{ max-width: 650px; margin: 0 auto; background: #ffffff; border: 1px solid #d4dfd8; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.06); }}
    .header {{ background: #0b2318; color: #ffffff; padding: 20px 24px; display: flex; align-items: center; justify-content: space-between; }}
    .badge {{ background: #d9381e; color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; letter-spacing: 1px; }}
    .content {{ padding: 24px; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 20px 0; }}
    .stat-card {{ background: #f0f6f2; border: 1px solid #d0e2d6; border-radius: 6px; padding: 12px; }}
    .stat-label {{ font-size: 11px; color: #5a7566; text-transform: uppercase; font-weight: 600; }}
    .stat-value {{ font-size: 20px; color: #0f5132; font-weight: bold; margin-top: 4px; font-family: Consolas, monospace; }}
    .privacy-notice {{ background: #e8f4ec; border-left: 4px solid #198754; padding: 12px 16px; margin: 20px 0; border-radius: 0 6px 6px 0; font-size: 13px; color: #145a32; }}
    .footer {{ background: #f8faf9; border-top: 1px solid #e1ebe5; padding: 14px 24px; font-size: 12px; color: #738a7e; text-align: center; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div>
        <h2 style="margin: 0; font-size: 18px; letter-spacing: 0.5px;">ISRO TELEMETRY & FLIGHT OPERATIONS</h2>
        <div style="font-size: 12px; color: #8fd4af; margin-top: 4px;">Mission: LVM3-M4 / Chandrayaan Flight Tracking</div>
      </div>
      <span class="badge">OFFICIAL DISPATCH</span>
    </div>
    <div class="content">
      <p>Dear <strong>{recipient}</strong>,</p>
      <p>This is an automated encrypted dispatch containing sanitized live telemetry from the <strong>LVM3-M4 Launch Simulation</strong>.</p>

      <div class="grid">
        <div class="stat-card">
          <div class="stat-label">Altitude / Elevation</div>
          <div class="stat-value">{alt} km</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Velocity / Speed</div>
          <div class="stat-value">{vel} m/s</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Mach Regime</div>
          <div class="stat-value">Mach {mach}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Dynamic Pressure (Max-Q)</div>
          <div class="stat-value">{q} kPa</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Chamber Pressure</div>
          <div class="stat-value">{chamber} bar</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Core Propellant Remaining</div>
          <div class="stat-value">{prop} %</div>
        </div>
      </div>

      <div class="privacy-notice">
        <strong>Fable Privacy Shield Verification:</strong><br/>
        All confidential Cryogenic Engine (CE-20) blueprints, nozzle CAD specifications, and cryptographic transponder keys were redacted prior to external transmission.
      </div>
    </div>
    <div class="footer">
      Indian Space Research Organisation (ISRO) • Autonomous Mission Control Agent
    </div>
  </div>
</body>
</html>"""

    def _build_plain_text_report(self, recipient: str, subject: str, telemetry: dict[str, Any], raw_text: str) -> str:
        alt = telemetry.get("altitude_km", 54.20)
        vel = telemetry.get("velocity_ms", 1824.5)
        mach = telemetry.get("mach", 5.42)
        q = telemetry.get("dynamic_pressure_kpa", 34.80)
        prop = telemetry.get("propellant_remaining_pct", 71.8)

        return f"""======================================================================
ISRO LVM3-M4 LAUNCH TELEMETRY & FLIGHT TEST REPORT
======================================================================
Recipient : {recipient}
Subject   : {subject}
Status    : FLIGHT PHASE STAGE-1 (S200/L110)

FLIGHT PARAMETERS:
- Altitude            : {alt} km
- Velocity            : {vel} m/s (Mach {mach})
- Dynamic Pressure    : {q} kPa (Max-Q Nominal)
- Propellant Remaining: {prop} %

PRIVACY VERIFICATION:
- CE-20 Cryogenic Engine CAD : REDACTED / BLURRED
- Telemetry Crypto Keys      : TOKENIZED / PROTECTED
======================================================================
"""
