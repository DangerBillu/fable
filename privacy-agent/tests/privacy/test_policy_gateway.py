import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from mcp.gateway import McpGateway
from runtime.policy import PolicyEngine
from runtime.state import ActionRequest, BrowserAction, PolicyDecision, SanitizedState
from runtime.tokenization import TokenVault


class PolicyGatewayTests(unittest.TestCase):
    def setUp(self):
        self.state = SanitizedState(
            page={"title": "Company Dashboard", "domain": "example.com"},
            elements=({"id": "settings_1", "label": "Settings", "type": "button"},),
            visible_text="Email EMAIL_001",
            privacy={"mode": "STRICT"},
        )

    def test_click_is_allowed(self):
        decision = PolicyEngine(mode="STRICT").evaluate(
            self.state,
            ActionRequest(BrowserAction.CLICK, element_id="settings_1"),
        )
        self.assertEqual(decision.decision, PolicyDecision.ALLOW)

    def test_type_sensitive_token_requires_approval_in_strict_mode(self):
        decision = PolicyEngine(mode="STRICT").evaluate(
            self.state,
            ActionRequest(BrowserAction.TYPE, element_id="recipient", text="EMAIL_001"),
        )
        self.assertEqual(decision.decision, PolicyDecision.REQUIRE_APPROVAL)

    def test_gateway_resolves_tokens_only_after_allow(self):
        vault = TokenVault()
        token = vault.tokenize(category=__import__("runtime.state").state.SensitiveCategory.EMAIL, value="john@example.com")
        gateway = McpGateway(vault)
        approved = PolicyEngine(mode="BALANCED").evaluate(
            self.state,
            ActionRequest(BrowserAction.TYPE, element_id="recipient", text=token),
            approved_by_user=True,
        )
        command = gateway.browser_command(approved)
        self.assertEqual(command["text"], "john@example.com")


if __name__ == "__main__":
    unittest.main()

