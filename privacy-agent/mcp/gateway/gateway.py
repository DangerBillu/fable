from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mcp.registry import McpRegistry
from runtime.state import ApprovedAction, BrowserAction, PolicyDecision
from runtime.tokenization import TokenVault


@dataclass
class McpGateway:
    vault: TokenVault
    registry: McpRegistry = field(init=False)

    def __post_init__(self) -> None:
        self.registry = McpRegistry(self.vault)

    def browser_command(self, approved: ApprovedAction) -> dict:
        if approved.decision != PolicyDecision.ALLOW:
            raise PermissionError(f"Action was not allowed: {approved.decision.value}")
        request = approved.request
        command = {"action": request.action.value.replace("browser.", "")}
        if request.element_id:
            command["element_id"] = request.element_id
        if request.text:
            command["text"] = self._resolve_tokens(request.text)
        if request.url:
            command["url"] = request.url
        if request.key:
            command["key"] = request.key
        if request.value:
            command["value"] = self._resolve_tokens(request.value)
        if request.delta_x is not None:
            command["deltaX"] = request.delta_x
        if request.delta_y is not None:
            command["deltaY"] = request.delta_y
        if request.action == BrowserAction.DONE:
            command["action"] = "done"
        return command

    def execute_tool(self, tool_name: str, **kwargs) -> dict[str, Any]:
        """Execute a registered J.A.R.V.I.S. MCP tool."""
        tool = self.registry.get_tool(tool_name)
        if not tool:
            raise KeyError(f"MCP Tool not found: {tool_name}")
        return tool.handler(**kwargs)

    def _resolve_tokens(self, text: str) -> str:
        resolved = text
        for word in text.split():
            token = word.strip(".,;:()[]{}")
            if self.vault.has(token):
                resolved = resolved.replace(token, self.vault.resolve(token))
        return resolved
