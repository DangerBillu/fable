(() => {
  "use strict";

  const chatMessages = document.getElementById("chat-messages");
  const chatInput = document.getElementById("chat-input");
  const chatForm = document.getElementById("chat-form");
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

  // Auto-resize textarea on input & submit on Enter (without Shift)
  chatInput.addEventListener("input", () => {
    chatInput.style.height = "auto";
    chatInput.style.height = `${Math.min(chatInput.scrollHeight, 80)}px`;
  });

  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.requestSubmit();
    }
  });

  // Handle Quick Chips
  document.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (chip && chip.dataset.prompt) {
      chatInput.value = chip.dataset.prompt;
      chatForm.requestSubmit();
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
            <button class="chip" data-prompt="Trigger stage separation on launch console">🚀 Stage Separation</button>
            <button class="chip" data-prompt="Email flight test results to arnav.goyal0713@gmail.com">📧 Email Flight Report</button>
            <button class="chip" data-prompt="Recalibrate engine gimbal on launch console">📐 Recalibrate Gimbal</button>
            <button class="chip" data-prompt="Emergency telemetry hold">⚠️ Emergency Hold</button>
          </div>
        </div>
      </div>
    `;
  });

  // Stop button
  btnStop.addEventListener("click", async () => {
    await chrome.runtime.sendMessage({ type: "STOP_AGENT" });
    setExecutingState(false);
    appendBotMessage("⏹️ Directive stopped by user.");
  });

  // Submit directive
  window.handleChatSubmit = async function (e) {
    if (e) e.preventDefault();
    const promptText = chatInput.value.trim();
    if (!promptText || isExecuting) return;

    // 1. Append user message
    appendUserMessage(promptText);
    chatInput.value = "";
    chatInput.style.height = "auto";

    // 2. Set executing state
    setExecutingState(true);
    showActionBanner(`Deploying FABLE Army for: "${promptText.slice(0, 30)}..."`);

    try {
      const response = await chrome.runtime.sendMessage({
        type: "START_AGENT",
        goal: promptText
      });

      if (!response?.ok && response?.error) {
        appendBotMessage(`❌ Error executing directive: ${response.error}`);
        setExecutingState(false);
        return;
      }
    } catch (err) {
      appendBotMessage(`❌ Communication error with background runtime: ${err.message}`);
      setExecutingState(false);
    }
  };

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
        <p>${text}</p>
        ${cardHtml}
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
      agentStatusText.textContent = "Army Executing Directive...";
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

  // Poll runtime status and stream execution results to chat
  let lastActionSeen = "";
  let lastApprovedCount = 0;

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

      // Check if a new action occurred
      if (stats.lastAction && stats.lastAction !== lastActionSeen && stats.lastAction !== "idle" && stats.lastAction !== "starting") {
        lastActionSeen = stats.lastAction;
        
        let actionDesc = `Executed MCP browser command: ${stats.lastAction}`;
        if (stats.lastAction === "click") {
          actionDesc = `🚀 [MCP PILOT] Successfully clicked element on page`;
        }
        
        appendBotMessage(`Directive executed successfully.`, {
          title: `MCP Action: ${stats.lastAction.toUpperCase()}`,
          desc: `${actionDesc} | Privacy Shield: Clean`
        });
      }
    } catch (_) {}
  }

  setInterval(pollStatus, 800);
  pollStatus();
})();
