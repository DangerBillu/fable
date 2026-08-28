const RUNTIME_URL = "http://127.0.0.1:8000/agent/step";
const MAX_STEPS = 12;

let running = false;
let sessionId = crypto.randomUUID();
let stepCount = 0;
let lastStats = {
  status: "Protected",
  mode: "STRICT",
  screenshots: 0,
  redacted: 0,
  tokenized: 0,
  blocked: 0,
  approved: 0,
  lastAction: "idle"
};

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "START_AGENT") {
    start(message.goal || "Open the settings page.")
      .then((result) => sendResponse(result))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }
  if (message?.type === "STOP_AGENT") {
    running = false;
    lastStats.lastAction = "stopped";
    sendResponse({ ok: true });
    return false;
  }
  if (message?.type === "GET_STATUS") {
    sendResponse({ ok: true, running, stats: lastStats });
    return false;
  }
  return false;
});

async function start(goal) {
  running = true;
  sessionId = crypto.randomUUID();
  stepCount = 0;
  lastStats.lastAction = "starting";
  loop(goal);
  return { ok: true, sessionId };
}

async function loop(goal) {
  while (running && stepCount < MAX_STEPS) {
    const result = await runStep(goal);
    if (result.status !== "ALLOW" || result.command?.action === "done") {
      running = false;
      break;
    }
    await delay(750);
  }
  running = false;
}

async function runStep(goal) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !tab.windowId) {
    throw new Error("No active tab available");
  }
  await ensureContentScript(tab.id);
  const dom = await sendTab(tab.id, { type: "CAPTURE_DOM_STATE" });
  const screenshotDataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
  lastStats.screenshots += 1;

  const response = await fetch(RUNTIME_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      user_instruction: goal,
      title: dom.title,
      url: dom.url,
      visible_text: dom.visible_text,
      elements: dom.elements,
      screenshot_data_url: screenshotDataUrl,
      approved_by_user: false
    })
  });
  if (!response.ok) {
    throw new Error(`Runtime rejected step: ${response.status}`);
  }
  const planned = await response.json();
  const privacy = planned.state?.privacy || {};
  lastStats.redacted += Number(privacy.redacted || 0);
  lastStats.tokenized += Number(privacy.findings || 0);
  lastStats.lastAction = planned.action || planned.command?.action || "none";

  if (planned.status === "REQUIRE_APPROVAL" || planned.status === "DENY") {
    lastStats.blocked += 1;
    await chrome.storage.session.set({ privacyAgentApproval: planned });
    return planned;
  }

  if (planned.command && planned.command.action !== "done") {
    const execution = await sendTab(tab.id, { type: "EXECUTE_APPROVED_COMMAND", command: planned.command });
    if (!execution.ok) {
      throw new Error(execution.error || "Command execution failed");
    }
    lastStats.approved += 1;
  }
  stepCount += 1;
  return planned;
}

async function ensureContentScript(tabId) {
  try {
    await sendTab(tabId, { type: "PING_PRIVACY_AGENT" });
  } catch (_error) {
    await chrome.scripting.executeScript({ target: { tabId }, files: ["src/dom/content.js"] });
  }
}

function sendTab(tabId, message) {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, message, (response) => {
      const error = chrome.runtime.lastError;
      if (error) {
        reject(new Error(error.message));
        return;
      }
      resolve(response);
    });
  });
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

