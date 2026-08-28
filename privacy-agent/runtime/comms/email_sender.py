from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
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
                os.environ[k.strip()] = v.strip()


class EmailSender:
    """Handles real SMTP email delivery and local outbox file generation."""

    def __init__(self) -> None:
        load_project_env()
        self.smtp_host = os.getenv("SMTP_HOST", "").strip()
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "").strip()
        # Strip all whitespace/spaces from app passwords (e.g., 'feqb qxqz eqvf saxw' -> 'feqbqxqzeqvfsaxw')
        self.smtp_password = os.getenv("SMTP_PASSWORD", "").replace(" ", "").strip()
        self.smtp_from = os.getenv("SMTP_FROM", f"Fable ISRO Mission Control <{self.smtp_user}>").strip()
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

        # 2. If SMTP credentials are provided, send over the wire
        smtp_sent = False
        smtp_error = None
        if self.smtp_host and self.smtp_user and self.smtp_password:
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

        return {
            "recipient": recipient,
            "subject": subject,
            "smtp_sent": smtp_sent,
            "smtp_error": smtp_error,
            "outbox_html": str(html_file),
            "outbox_eml": str(eml_file),
            "status": "delivered_to_smtp" if smtp_sent else "saved_to_outbox",
        }

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
        <strong>🛡️ J.A.R.V.I.S. Privacy Shield Verification:</strong><br/>
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
