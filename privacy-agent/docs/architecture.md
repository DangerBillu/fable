# Architecture

Phase 1 implements a local privacy firewall around a browser-use agent:

1. Chrome extension captures DOM, accessibility-oriented element data, bounding boxes, and the visible tab screenshot.
2. The local FastAPI runtime receives raw observation data over localhost only.
3. `runtime.privacy.PrivacyFirewall` sanitizes DOM text, sensitive form metadata, OCR text when supplied, and screenshot regions before planner access.
4. `agent.planner.Planner` accepts only `SanitizedState`.
5. `runtime.policy.PolicyEngine` independently evaluates the action.
6. `mcp.gateway.McpGateway` accepts only `ApprovedAction` and resolves local tokens immediately before execution.
7. The extension executes the approved browser command and observes again.

The reasoning component is treated as untrusted. It can propose an action, but it cannot decide what data it sees or what tools it may use.

