import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent.loop import AgentLoop
from agent.planner import Planner
from mcp.gateway import McpGateway
from runtime.audit import AuditLogger
from runtime.policy import PolicyEngine
from runtime.privacy import ImageRedactor, PrivacyDetector, PrivacyFirewall
from runtime.state import RawDom, RawObservation
from runtime.tokenization import TokenVault


class ArticleSummaryEmailTests(unittest.TestCase):
    def test_article_summary_email_uses_sanitized_page_text(self):
        vault = TokenVault()
        loop = AgentLoop(
            firewall=PrivacyFirewall(
                detector=PrivacyDetector(vault),
                redactor=ImageRedactor(),
            ),
            planner=Planner(),
            policy=PolicyEngine(mode="STRICT"),
            gateway=McpGateway(vault),
            audit=AuditLogger(ROOT / "tmp-article-audit.log"),
        )

        article_text = (
            "A new city transit study found that commuters saved time when buses received priority at busy junctions. "
            "Researchers reported that average journey times fell by 18 percent during peak hours because signals changed based on live congestion data. "
            "The system could also reduce emissions by keeping buses moving instead of waiting through repeated traffic light cycles. "
            "Contact the author at reporter@example.com for additional interview notes and background details. "
            "Officials said the next phase will expand testing to school routes and hospital corridors."
        )

        with patch("runtime.comms.email_sender.EmailSender.send_article_summary_email") as send:
            send.return_value = {
                "recipient": "reader@example.com",
                "subject": "Fable summary: Transit Study",
                "smtp_configured": True,
                "smtp_sent": True,
                "smtp_error_code": None,
                "smtp_error": None,
                "outbox_html": "outbox/latest_article_summary.html",
                "outbox_eml": "outbox/latest_article_summary.eml",
                "status": "delivered_to_smtp",
            }
            result = loop.step(
                RawObservation(
                    session_id="article-summary",
                    raw_dom=RawDom(
                        title="Transit Study",
                        url="https://news.example.test/transit-study",
                        visible_text=article_text,
                        elements=(),
                    ),
                ),
                "Summarize this article and email it to reader@example.com",
            )

        self.assertEqual(result["status"], "ALLOW")
        self.assertEqual(result["command"]["action"], "done")
        self.assertIn("tool_result", result)
        _args, kwargs = send.call_args
        self.assertEqual(kwargs["recipient"], "reader@example.com")
        self.assertEqual(kwargs["article_url"], "https://news.example.test/transit-study")
        self.assertIn("commuters saved time", kwargs["summary"])
        self.assertNotIn("reporter@example.com", kwargs["summary"])
        self.assertIn("EMAIL_", kwargs["source_excerpt"])


if __name__ == "__main__":
    unittest.main()
