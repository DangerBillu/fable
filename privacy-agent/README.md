# Fable

Local, privacy-first browser assistant. Fable reads the current page, redacts sensitive data, plans safe browser actions, and can email sanitized summaries through SMTP or the local outbox.

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
- Article summary email flow for real reading workflows.

## Run

Create the venv once:

```powershell
cd C:\Users\yousi\OneDrive\Documents\fable\privacy-agent
C:\Users\yousi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m venv .venv
```

Start it and install dependencies:

```powershell
cd C:\Users\yousi\OneDrive\Documents\fable\privacy-agent
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Start the app:

```powershell
cd C:\Users\yousi\OneDrive\Documents\fable\privacy-agent
.\.venv\Scripts\Activate.ps1
python -m uvicorn runtime.server:app --host 127.0.0.1 --port 8000
```

If you have not installed the FastAPI dependencies yet, run the dependency-free local server:

```powershell
cd C:\Users\yousi\OneDrive\Documents\fable\privacy-agent
.\.venv\Scripts\Activate.ps1
python -m runtime.stdlib_server
```

Load `privacy-agent/extension` as an unpacked Chrome extension. Open an article in Chrome, then run this task from the Fable popup:

```text
Summarize this article and email it to me
```

You can also open `demo/company-dashboard.html` and run `Open the settings page.` to test browser actions.

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
cd C:\Users\yousi\OneDrive\Documents\fable\privacy-agent
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s tests
```

The tests focus on false negatives for known sensitive patterns, tokenization, prompt-injection separation, policy gating, MCP token resolution, browser actions, and article summary emails.
