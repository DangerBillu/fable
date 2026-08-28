# Privacy Boundary

Raw data classes:

- `RawScreenshot`
- `RawDom`
- `RawObservation`

Sanitized classes:

- `SanitizedScreenshot`
- `SanitizedDom`
- `SanitizedState`
- `SanitizedObservation`

The planner and Ollama adapter accept only `SanitizedState`. Sensitive values are replaced with local tokens such as `EMAIL_001` and `PHONE_001`. The mapping remains in `TokenVault` and is resolved only by the local MCP gateway after the policy engine allows an action.

Classification levels are configurable:

- `PUBLIC`
- `INTERNAL`
- `CONFIDENTIAL`
- `RESTRICTED`
- `SECRET`

Fail closed rule: if redaction or policy evaluation fails, data is blocked from the model or the action is denied.

