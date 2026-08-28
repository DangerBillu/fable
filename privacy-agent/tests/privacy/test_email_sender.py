import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from runtime.comms.email_sender import EmailSender, _clean_env_value, _normalize_secret


class EmailSenderTests(unittest.TestCase):
    def test_env_values_support_quotes_and_inline_comments(self):
        self.assertEqual(_clean_env_value('"smtp.gmail.com"'), "smtp.gmail.com")
        self.assertEqual(_clean_env_value("587 # tls port"), "587")

    def test_app_password_whitespace_is_removed(self):
        self.assertEqual(_normalize_secret("abcd efgh\tijkl mnop"), "abcdefghijklmnop")

    def test_smtp_user_can_be_inferred_from_from_address(self):
        with patch.dict(
            "os.environ",
            {
                "SMTP_HOST": "smtp.gmail.com",
                "SMTP_PORT": "587",
                "SMTP_USER": "",
                "SMTP_PASSWORD": "abcd efgh ijkl mnop",
                "SMTP_FROM": "Fable <sender@example.com>",
            },
        ):
            with patch("runtime.comms.email_sender.load_project_env", return_value=None):
                sender = EmailSender()

        self.assertEqual(sender.smtp_user, "sender@example.com")

    def test_blocked_socket_reports_actionable_error_code(self):
        blocked = OSError("An attempt was made to access a socket in a way forbidden by its access permissions")
        blocked.winerror = 10013

        with patch.dict(
            "os.environ",
            {
                "SMTP_HOST": "smtp.gmail.com",
                "SMTP_PORT": "587",
                "SMTP_USER": "sender@example.com",
                "SMTP_PASSWORD": "abcd efgh ijkl mnop",
                "SMTP_FROM": "Fable <sender@example.com>",
            },
        ):
            with patch("runtime.comms.email_sender.load_project_env", return_value=None):
                with patch("runtime.comms.email_sender.smtplib.SMTP", side_effect=blocked):
                    result = EmailSender().send_telemetry_email(
                        recipient="recipient@example.com",
                        subject="Test Report",
                        telemetry_data={},
                    )

        self.assertFalse(result["smtp_sent"])
        self.assertTrue(result["smtp_configured"])
        self.assertEqual(result["smtp_error_code"], "smtp_blocked")
        self.assertEqual(result["status"], "saved_to_outbox")
        self.assertTrue(Path(result["outbox_eml"]).exists())


if __name__ == "__main__":
    unittest.main()
