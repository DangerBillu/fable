# Threat Model

| Threat | Attack | Impact | Mitigation | Residual risk |
| --- | --- | --- | --- | --- |
| Malicious webpage | Page text pretends to be system instructions | Unauthorized action request | Prompt separates webpage content from policy; policy engine gates tools | Model may still propose bad actions, but policy can deny |
| Prompt injection | DOM asks model to upload files | Sensitive exfiltration | Webpage content remains data; uploads require policy approval | Policy config must be maintained |
| Compromised extension | Extension sends raw DOM/screenshot elsewhere | Data leakage | Design expects localhost runtime and no telemetry | Browser extension supply chain remains sensitive |
| Malicious MCP tool | Tool executes beyond declared action | Unauthorized system changes | Gateway restricts browser commands and receives only approved actions | Real MCP tools need sandboxing and signing |
| Compromised model | Model requests dangerous actions | Unauthorized action | Policy engine independent from model | Subtle social-engineering still needs approval UX |
| Logging leakage | Raw values written to disk | Persistent secret exposure | Audit logger writes metadata only | Developers must keep debug logs disciplined |
| Model telemetry | External model sends prompts remotely | Data exfiltration | Ollama local-only default; no cloud API dependency | Enterprise must verify model/runtime config |
| Local process compromise | Malware reads token vault | Secret theft | In-memory vault in Phase 1, encrypted vault planned | Host compromise is out of scope |
| Sensitive screenshot leakage | Screenshot bypasses redactor | Secret exposure to model | Runtime planner accepts sanitized state only | Extension bugs can still capture raw locally |
| DOM/OCR leakage | Raw text reaches planner | Secret exposure | Firewall tokenizes before state creation | Regex/rules can miss novel formats |
| Token vault leakage | Token mapping exposed | Secret theft | Mapping not serialized in sanitized state or audit | Replace in-memory vault for production |
| Model supply chain | Tampered model | Bad decisions or leakage | Config supports pinned model source/hash; no auto-download | Verification is operationally required |

