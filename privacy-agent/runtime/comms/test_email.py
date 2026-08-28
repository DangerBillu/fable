from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.comms.email_sender import EmailSender, load_project_env


def main():
    load_project_env()
    recipient = sys.argv[1] if len(sys.argv) > 1 else os.getenv("SMTP_USER", "")
    if not recipient:
        print("Usage: python -m runtime.comms.test_email your_email@gmail.com")
        print("\nChecking your current .env settings:")
        print(f"  SMTP_HOST     : {os.getenv('SMTP_HOST', '(empty)')}")
        print(f"  SMTP_USER     : {os.getenv('SMTP_USER', '(empty)')}")
        print(f"  SMTP_PASSWORD : {'*' * len(os.getenv('SMTP_PASSWORD', '')) if os.getenv('SMTP_PASSWORD') else '(empty)'}")
        return

    print("=" * 65)
    print("[ISRO J.A.R.V.I.S. EMAIL DISPATCH TESTER]")
    print("=" * 65)
    print(f"Target Recipient : {recipient}")
    print(f"SMTP Host        : {os.getenv('SMTP_HOST', '(not configured)')}")
    print(f"SMTP User        : {os.getenv('SMTP_USER', '(not configured)')}")
    print("=" * 65)

    sender = EmailSender()
    res = sender.send_telemetry_email(
        recipient=recipient,
        subject="ISRO LVM3-M4 Live Test Dispatch",
        telemetry_data={
            "altitude_km": 54.20,
            "velocity_ms": 1824.5,
            "mach": 5.42,
            "dynamic_pressure_kpa": 34.80,
            "chamber_pressure_bar": 58.4,
            "propellant_remaining_pct": 71.8,
        },
    )

    print(f"\n[STATUS] {res['status'].upper()}")
    print(f"  * Local HTML Outbox : {res['outbox_html']}")
    print(f"  * Local EML File    : {res['outbox_eml']}")

    if res.get("smtp_sent"):
        print(f"\n[SUCCESS] Real email was delivered via {os.getenv('SMTP_HOST')} to {recipient}!")
        print("Check your inbox (and spam/promotions folder).")
    else:
        print("\n[ERROR / NOTICE] Email was NOT sent over the internet.")
        if res.get("smtp_error"):
            print(f"  SMTP Error: {res['smtp_error']}")
        print("\nTo send real emails to your Gmail/Outlook inbox:")
        print("  1. Open the .env file in your editor.")
        print("  2. Fill in SMTP_HOST, SMTP_USER, and SMTP_PASSWORD.")
        print("  3. Run this command again.")
    print("=" * 65)


if __name__ == "__main__":
    main()
