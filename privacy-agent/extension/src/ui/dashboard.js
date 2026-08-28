(() => {
  "use strict";

  const chatMessages = document.getElementById("chat-messages");
  const chatInput = document.getElementById("chat-input");
  const btnSend = document.getElementById("btn-send");
  const btnStop = document.getElementById("btn-stop");
  const btnClearChat = document.getElementById("btn-clear-chat");
  const liveActionBanner = document.getElementById("live-action-banner");
  const actionBannerText = document.getElementById("action-banner-text");
  const agentStatusText = document.getElementById("agent-status-text");

  const statRedacted = document.getElementById("stat-redacted");
  const statFaces = document.getElementById("stat-faces");
  const statApproved = document.getElementById("stat-approved");

  let isExecuting = false;
  let lastSeenTs = 0;

  // Auto-resize textarea on input
  chatInput.addEventListener("input", () => {
    chatInput.style.height = "auto";
    chatInput.style.height = `${Math.min(chatInput.scrollHeight, 80)}px`;
  });

  // Enter to send (Shift+Enter for newline)
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendDirective();
    }
  });

  // Click Send button
  btnSend.addEventListener("click", (e) => {
    e.preventDefault();
    sendDirective();
  });

  // Click Quick Chips
  document.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (chip && chip.dataset.prompt) {
      chatInput.value = chip.dataset.prompt;
      sendDirective();
    }
  });

  // Clear chat
  btnClearChat.addEventListener("click", () => {
    chatMessages.innerHTML = `
      <div class="msg-row bot-row">
        <div class="msg-avatar">F</div>
        <div class="msg-bubble bot-bubble">
          <p><strong>FABLE Copilot ready.</strong> What mission directive or webpage action should I perform?</p>
          <div class="quick-chips">
            <button class="chip" data-prompt="Click the stage separation button">🚀 Stage Separation</button>
            <button class="chip" data-prompt="Click the send telemetry report button">📧 Send Report</button>
            <button class="chip" data-prompt="Click the gimbal recalibration button">📐 Gimbal Recal</button>
            <button class="chip" data-prompt="Scroll down on this page">⬇️ Scroll Down</button>
          </div>
        </div>
      </div>
    `;
    lastSeenTs = Date.now();
  });

  // Stop button
  btnStop.addEventListener("click", async () => {
    await chrome.runtime.sendMessage({ type: "STOP_AGENT" });
    setExecutingState(false);
    appendBotMessage("⏹️ Directive stopped by user.");
  });

  async function sendDirective() {
    const promptText = chatInput.value.trim();
    if (!promptText || isExecuting) return;

    // 1. Immediately render user message in chat
    appendUserMessage(promptText);
    chatInput.value = "";
    chatInput.style.height = "auto";

    // 2. Set executing state & live action banner
    setExecutingState(true);
    showActionBanner(`Processing: "${promptText.slice(0, 32)}..."`);

    try {
      const messageType = shouldUseDirectAction(promptText) ? "DIRECT_ACTION" : "START_AGENT";
      const response = await chrome.runtime.sendMessage({
        type: messageType,
        goal: promptText
      });

      if (!response?.ok && response?.error) {
        // Fallback to direct action mode
        const directResp = await chrome.runtime.sendMessage({
          type: "DIRECT_ACTION",
          goal: promptText
        });
        if (!directResp?.ok && directResp?.error) {
          appendBotMessage(`❌ Direct action error: ${directResp.error}`);
          setExecutingState(false);
        }
      }
    } catch (err) {
      // If service worker call failed, attempt direct action
      try {
        const directResp = await chrome.runtime.sendMessage({
          type: "DIRECT_ACTION",
          goal: promptText
        });
        if (!directResp?.ok) {
          appendBotMessage(`❌ Communication error: ${err.message}`);
          setExecutingState(false);
        }
      } catch (dErr) {
        appendBotMessage(`❌ Execution failed: ${dErr.message}`);
        setExecutingState(false);
      }
    }
  }

  function shouldUseDirectAction(text) {
    return /\b(click|press|tap|hit|push|trigger|activate|select|type|enter|write|fill|input|scroll|go back|navigate back|windspeed|wind speed|tally|datapoint|datapoints|mcp)\b/i.test(text);
  }

  function appendUserMessage(text) {
    const row = document.createElement("div");
    row.className = "msg-row user-row";
    row.innerHTML = `
      <div class="msg-avatar">U</div>
      <div class="msg-bubble user-bubble">${escapeHtml(text)}</div>
    `;
    chatMessages.appendChild(row);
    scrollToBottom();
  }

  function appendBotMessage(text, actionCard = null) {
    const row = document.createElement("div");
    row.className = "msg-row bot-row";

    let cardHtml = "";
    if (actionCard) {
      cardHtml = `
        <div class="action-card">
          <div class="action-title">${escapeHtml(actionCard.title)}</div>
          <div class="action-desc">${escapeHtml(actionCard.desc)}</div>
        </div>
      `;
    }

    row.innerHTML = `
      <div class="msg-avatar">F</div>
      <div class="msg-bubble bot-bubble">
        <p>${escapeHtml(text)}</p>
        ${cardHtml}
      </div>
    `;
    chatMessages.appendChild(row);
    scrollToBottom();
  }

  function appendActionStepMessage(stepText) {
    const row = document.createElement("div");
    row.className = "msg-row bot-row";
    row.innerHTML = `
      <div class="msg-avatar">⚡</div>
      <div class="msg-bubble bot-bubble" style="background: #091710; border-color: #173f2b; font-size: 12px;">
        <span style="color: #00ff88; font-weight: bold;">[ACTION STEP]</span> ${escapeHtml(stepText)}
      </div>
    `;
    chatMessages.appendChild(row);
    scrollToBottom();
  }

  function setExecutingState(executing) {
    isExecuting = executing;
    if (executing) {
      btnSend.style.display = "none";
      btnStop.style.display = "flex";
      agentStatusText.textContent = "Copilot Executing Directive...";
    } else {
      btnSend.style.display = "flex";
      btnStop.style.display = "none";
      liveActionBanner.style.display = "none";
      agentStatusText.textContent = "Shield Active & Ready";
    }
  }

  function showActionBanner(text) {
    liveActionBanner.style.display = "flex";
    actionBannerText.textContent = text;
  }

  function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str || "";
    return div.innerHTML;
  }

  // Poll background service worker for state & new messages
  async function pollStatus() {
    try {
      const resp = await chrome.runtime.sendMessage({ type: "GET_STATUS" });
      if (!resp?.ok) return;

      const stats = resp.stats || {};
      statRedacted.textContent = String((stats.redacted || 0) + (stats.tokenized || 0));
      statFaces.textContent = String(stats.facesBlurred || 0);
      statApproved.textContent = String(stats.approved || 0);

      if (resp.running && !isExecuting) {
        setExecutingState(true);
      } else if (!resp.running && isExecuting) {
        setExecutingState(false);
      }

      // Render new messages from chatLog
      if (Array.isArray(resp.chatLog)) {
        const newMsgs = resp.chatLog.filter((m) => m.ts > lastSeenTs);
        for (const msg of newMsgs) {
          lastSeenTs = Math.max(lastSeenTs, msg.ts);
          if (msg.role === "user") {
            // Already rendered locally
          } else if (msg.role === "action") {
            appendActionStepMessage(msg.text);
          } else if (msg.role === "bot") {
            appendBotMessage(msg.text);
          }
        }
      }
    } catch (_) {}
  }

  setInterval(pollStatus, 500);
  pollStatus();
})();
