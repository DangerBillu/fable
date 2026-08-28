# Privacy Agent

Local, privacy-first browser agent MVP. The product principle is a privacy firewall surrounding a computer-use agent: the model sees sanitized state, and the policy engine controls actions.

## Phase 1 Contents

- Chrome Manifest V3 extension with DOM capture, screenshot capture, dashboard, and kill switch.
- Local FastAPI runtime at `127.0.0.1:8000`.
- Deterministic privacy detector for email, phone, credit cards, JWTs, API keys, auth headers, private keys, sensitive input fields, and private-document hints.
- Local token vault.
- Screenshot redaction with Pillow.
- Ollama-compatible planner adapter, disabled by default with deterministic fallback.
- Independent policy engine.
- MCP-style gateway that only accepts approved actions.
- Privacy-preserving audit log.
- Synthetic demo page at `demo/company-dashboard.html`.

## Run

```powershell
cd privacy-agent
python -m pip install -r requirements.txt
python -m uvicorn runtime.server:app --host 127.0.0.1 --port 8000
```

If you have not installed the FastAPI dependencies yet, run the dependency-free local server:

```powershell
cd privacy-agent
python -m runtime.stdlib_server
```

Load `privacy-agent/extension` as an unpacked Chrome extension, open `demo/company-dashboard.html`, and start the agent from the extension popup with the goal `Open the settings page.`

Ollama is optional:

```powershell
$env:USE_OLLAMA="1"
$env:OLLAMA_BASE_URL="http://127.0.0.1:11434"
$env:OLLAMA_MODEL="qwen3:8b"
python -m uvicorn runtime.server:app --host 127.0.0.1 --port 8000
```

No cloud model, telemetry, or remote screenshot processing is used.

## Test

```powershell
cd privacy-agent
python -m unittest discover -s tests
```

The tests focus on false negatives for known sensitive patterns, tokenization, prompt-injection separation, policy gating, MCP token resolution, and the company-dashboard demo path.
