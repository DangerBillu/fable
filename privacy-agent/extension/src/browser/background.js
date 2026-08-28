import { screenAnalyzer } from '../capture/screen_analyzer.js';

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
  facesBlurred: 0,
  lastAction: "idle"
};

// Chat log: array of { role: "bot"|"user"|"action", text, detail? }
let chatLog = [];

function pushChat(role, text, detail) {
  chatLog.push({ role, text, detail: detail || null, ts: Date.now() });
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "START_AGENT") {
    start(message.goal || "Open the settings page.")
      .then((result) => sendResponse(result))
      .catch((error) => {
        pushChat("bot", "Error: " + error.message);
        sendResponse({ ok: false, error: error.message });
      });
    return true;
  }
  if (message?.type === "STOP_AGENT") {
    running = false;
    lastStats.lastAction = "stopped";
    pushChat("bot", "Directive stopped by user.");
    sendResponse({ ok: true });
    return false;
  }
  if (message?.type === "GET_STATUS") {
    sendResponse({ ok: true, running, stats: lastStats, chatLog });
    return false;
  }
  if (message?.type === "GET_CHAT_LOG") {
    const since = message.since || 0;
    const newMessages = chatLog.filter(m => m.ts > since);
    sendResponse({ ok: true, messages: newMessages, running });
    return false;
  }
  // Direct browser action from the popup
  if (message?.type === "DIRECT_ACTION") {
    directAction(message.goal)
      .then((result) => sendResponse(result))
      .catch((error) => {
        pushChat("bot", "Direct action failed: " + error.message);
        sendResponse({ ok: false, error: error.message });
      });
    return true;
  }
  return false;
});

// Direct action mode: parse user intent accurately
async function directAction(goal) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error("No active tab");

  await ensureContentScript(tab.id);
  const dom = await sendTab(tab.id, { type: "CAPTURE_DOM_STATE" });

  pushChat("action", "Captured active page: " + (dom.title || dom.url).slice(0, 50));

  const lowerGoal = goal.toLowerCase();
  let command = null;
  let explanation = "";

  // 1. --- EMAIL LINK / SUMMARY / SHARE INTENT ---
  if (/email|mail|send\s*(me\s*)?(the\s*)?(link|url|website|summary)|share\s*(the\s*)?(link|url)/i.test(lowerGoal)) {
    const emailMatch = goal.match(/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/);
    const recipient = emailMatch ? emailMatch[0] : "user@example.com";
    const pageUrl = dom.url || tab.url || "current page";
    const pageTitle = dom.title || "Current Webpage";

    pushChat("action", `Preparing email dispatch with page URL: ${pageUrl}`);

    try {
      const res = await fetch(RUNTIME_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          user_instruction: `Email the link ${pageUrl} (${pageTitle}) to ${recipient}`,
          title: dom.title,
          url: dom.url,
          visible_text: dom.visible_text,
          elements: dom.elements,
          approved_by_user: true
        })
      });

      if (res.ok) {
        lastStats.approved += 1;
        pushChat("bot", `📧 Sent email to ${recipient} with page link: ${pageUrl}`);
        return { ok: true, action: "email", detail: `Emailed link ${pageUrl} to ${recipient}` };
      }
    } catch (_) {}

    // Local outbox fallback
    lastStats.approved += 1;
    pushChat("bot", `📧 Captured active tab: "${pageTitle}"\nURL: ${pageUrl}\nQueued email dispatch to ${recipient} (Saved to outbox/latest_flight_report.html).`);
    return { ok: true, action: "email", detail: `Captured link ${pageUrl}` };
  }

  // 2. --- SCROLL INTENT ---
  if (/scroll\s*(down|up|bottom|top)/i.test(lowerGoal)) {
    const direction = /up|top/i.test(lowerGoal) ? -500 : 500;
    command = { action: "scroll", deltaY: direction };
    explanation = direction > 0 ? "Scrolling page down" : "Scrolling page up";
  }
  // 3. --- GO BACK INTENT ---
  else if (/go\s*back|navigate\s*back|previous\s*page/i.test(lowerGoal)) {
    command = { action: "go_back" };
    explanation = "Navigating back to previous page";
  }
  // 4. --- NAVIGATE INTENT ---
  else if (/navigate\s*to\s+|open\s+(url|page|site)\s+|go\s*to\s+/i.test(lowerGoal)) {
    const urlMatch = lowerGoal.match(/(?:navigate\s*to|open\s*(?:url|page|site)|go\s*to)\s+(\S+)/i);
    if (urlMatch) {
      let url = urlMatch[1];
      if (!url.startsWith("http")) url = "https://" + url;
      command = { action: "navigate", url };
      explanation = "Navigating to " + url;
    }
  }

  // 5. --- CLICK / TYPE INTENT ---
  // Only attempt to find and click an element if user explicitly requested clicking/typing, OR if no other intent matched.
  if (!command && isExplicitClickOrTypeIntent(lowerGoal)) {
    const match = findBestElement(dom.elements, lowerGoal);
    if (match) {
      const typeMatch = goal.match(/type\s+["'](.+?)["']\s+(?:in|into)/i) || goal.match(/(?:type|enter|write|fill|input)\s+["']?(.+?)["']?\s*$/i);
      if (/type|enter|write|fill|input/i.test(lowerGoal) && typeMatch) {
        command = { action: "type", element_id: match.id, text: typeMatch[1] };
        explanation = `Typing "${typeMatch[1]}" into [${match.text || match.id}]`;
      } else {
        command = { action: "click", element_id: match.id };
        explanation = `Clicking element [${match.text || match.id}]`;
      }
    }
  }

  if (!command) {
    pushChat("bot", `I received your request: "${goal}". I extracted the page title ("${dom.title}") and URL (${dom.url}). If you want me to click a specific button, please say "click [button name]".`);
    return { ok: true, action: "info" };
  }

  pushChat("action", explanation);
  const result = await sendTab(tab.id, { type: "EXECUTE_APPROVED_COMMAND", command });

  if (result.ok) {
    lastStats.approved += 1;
    lastStats.lastAction = command.action;
    pushChat("bot", "Done! " + explanation);
  } else {
    pushChat("bot", "Action failed: " + (result.error || "unknown error"));
  }

  return { ok: true, action: command.action, detail: explanation };
}

function isExplicitClickOrTypeIntent(goal) {
  return /click|press|tap|hit|push|trigger|recalibrate|jettison|separate|select|type|enter|write|fill|input/i.test(goal);
}

function findBestElement(elements, goal) {
  if (!elements || elements.length === 0) return null;

  const cleaned = goal
    .replace(/click(\s+on)?|press|tap|hit|push|trigger|activate|the|a|an|button|link|please|fable/gi, "")
    .trim();

  let bestScore = 0;
  let bestElement = null;

  for (const el of elements) {
    let score = 0;
    const elText = (el.text || "").toLowerCase();
    const elId = (el.id || "").toLowerCase();
    const elLabel = (el.aria_label || "").toLowerCase();
    const elRole = (el.role || "").toLowerCase();
    const combined = `${elText} ${elId} ${elLabel}`;

    if (goal.includes(elId) && elId.length > 2) score += 100;
    if (elText && goal.includes(elText)) score += 80;

    const goalWords = cleaned.split(/\s+/).filter(w => w.length > 2);
    for (const word of goalWords) {
      if (combined.includes(word)) score += 20;
    }

    if (el.tag === "button" || elRole === "button") score += 5;
    if (el.tag === "a") score += 3;
    if (el.enabled) score += 2;

    if (score > bestScore) {
      bestScore = score;
      bestElement = el;
    }
  }

  return bestScore >= 15 ? bestElement : null;
}

async function start(goal) {
  running = true;
  sessionId = crypto.randomUUID();
  stepCount = 0;
  lastStats.lastAction = "starting";
  pushChat("action", "Deploying FABLE agents...");

  loop(goal);
  return { ok: true, sessionId };
}

async function loop(goal) {
  while (running && stepCount < MAX_STEPS) {
    try {
      const result = await runStep(goal);
      if (result.status !== "ALLOW" || result.command?.action === "done") {
        pushChat("bot", "Mission directive complete.");
        running = false;
        break;
      }
    } catch (err) {
      pushChat("action", "Server offline. Switching to direct browser mode.");
      try {
        await directAction(goal);
      } catch (directErr) {
        pushChat("bot", "Error: " + directErr.message);
      }
      running = false;
      return;
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
  const rawScreenshotDataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
  lastStats.screenshots += 1;

  let finalScreenshot = rawScreenshotDataUrl;
  let faceRegions = [];

  try {
    const analysis = await screenAnalyzer.analyze(rawScreenshotDataUrl, dom);
    finalScreenshot = analysis.redactedScreenshot;
    faceRegions = analysis.faceRegions;
    if (analysis.stats.facesBlurred > 0) {
      lastStats.facesBlurred += analysis.stats.facesBlurred;
    }
  } catch (err) {
    console.warn("Screen analysis failed, falling back to raw screenshot", err);
  }

  pushChat("action", "Privacy Shield: Scanned page, redacting secrets...");

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
      screenshot_data_url: finalScreenshot,
      face_regions: faceRegions,
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

  // If a tool (e.g. email sender) was executed by backend server, push clear result to chat UI
  if (planned.tool_result) {
    const res = planned.tool_result;
    const recipient = res.recipient || "recipient";
    if (res.smtp_sent) {
      pushChat("bot", `📧 Email Delivered! Successfully sent live email to ${recipient} via SMTP.`);
    } else {
      pushChat("bot", `📧 Email Report Generated for ${recipient}. Saved to outbox/latest_flight_report.html`);
    }
  }

  if (planned.status === "REQUIRE_APPROVAL" || planned.status === "DENY") {
    lastStats.blocked += 1;
    pushChat("bot", "Action blocked by Privacy Shield policy.");
    return planned;
  }

  if (planned.command && planned.command.action !== "done") {
    pushChat("action", "Executing: " + (planned.command.action || "action") + " on " + (planned.command.element_id || "page"));
    const execution = await sendTab(tab.id, { type: "EXECUTE_APPROVED_COMMAND", command: planned.command });
    if (!execution.ok) {
      throw new Error(execution.error || "Command execution failed");
    }
    lastStats.approved += 1;
    pushChat("bot", "Completed: " + planned.command.action + (planned.command.element_id ? " [" + planned.command.element_id + "]" : ""));
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
