# Security

Non-negotiable boundaries implemented in Phase 1:

- Raw screenshots are accepted only by the local runtime and redacted before they can become model context.
- Planner and Ollama adapters reject inputs that are not marked `SanitizedState`.
- Policy decisions are outside the model.
- MCP commands are created only from `ApprovedAction`.
- Audit logs record metadata, policy decisions, and targets, not screenshots, raw DOM secrets, OCR secrets, tokens, or credentials.
- Fail-closed behavior denies actions when state is not sanitized or when the policy engine cannot classify the request.

Current limitations:

- OCR uses a local Tesseract CLI if provisioned; if unavailable, Phase 1 relies on DOM and deterministic rules.
- The token vault is in-memory for MVP use. Enterprise deployment should replace it with an encrypted, process-isolated local store.
- VLM support is intentionally disabled in Phase 1.

