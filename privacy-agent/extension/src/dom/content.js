(() => {
  "use strict";

  const INTERACTIVE_SELECTOR = [
    "a[href]",
    "button",
    "input",
    "textarea",
    "select",
    "[contenteditable='true']",
    "[role='button']",
    "[role='link']",
    "[role='textbox']",
    "[role='menuitem']",
    "[tabindex]"
  ].join(",");

  // Inject visual click pulse style
  const styleEl = document.createElement("style");
  styleEl.textContent = `
    @keyframes fablePulse {
      0% { box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.8), 0 0 10px rgba(0, 255, 136, 0.6); outline: 3px solid #00ff88; }
      50% { box-shadow: 0 0 0 12px rgba(0, 255, 136, 0.3), 0 0 20px rgba(0, 255, 136, 0.8); outline: 3px solid #00ff88; }
      100% { box-shadow: 0 0 0 0 rgba(0, 255, 136, 0), 0 0 0 rgba(0, 255, 136, 0); outline: none; }
    }
    .fable-agent-active-target {
      animation: fablePulse 1.2s ease-out !important;
      transition: outline 0.2s ease !important;
    }
  `;
  document.head.appendChild(styleEl);

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type === "PING_PRIVACY_AGENT") {
      sendResponse({ ok: true });
      return false;
    }
    if (message?.type === "CAPTURE_DOM_STATE") {
      sendResponse(captureDomState());
      return false;
    }
    if (message?.type === "EXECUTE_APPROVED_COMMAND") {
      executeCommand(message.command)
        .then((result) => sendResponse({ ok: true, result }))
        .catch((error) => sendResponse({ ok: false, error: error.message }));
      return true;
    }
    return false;
  });

  function captureDomState() {
    return {
      title: document.title || "",
      url: location.href,
      visible_text: visibleText(document.body).slice(0, 5000),
      elements: Array.from(document.querySelectorAll(INTERACTIVE_SELECTOR))
        .filter(isVisible)
        .slice(0, 250)
        .map(toPayload)
    };
  }

  function toPayload(element, index) {
    const rect = element.getBoundingClientRect();
    const id = stableId(element, index);
    element.dataset.privacyAgentId = id;
    return {
      id,
      tag: element.tagName.toLowerCase(),
      role: element.getAttribute("role"),
      aria_label: element.getAttribute("aria-label"),
      text: safeText(element),
      input_type: element.getAttribute("type"),
      placeholder: element.getAttribute("placeholder"),
      autocomplete: element.getAttribute("autocomplete"),
      bbox: [rect.left, rect.top, rect.width, rect.height],
      enabled: !element.disabled,
      href: element.href || null,
      value: shouldSendValue(element) ? element.value || "" : null,
      metadata: {
        name: element.getAttribute("name"),
        id_attr: element.getAttribute("id")
      }
    };
  }

  function shouldSendValue(element) {
    const tag = element.tagName.toLowerCase();
    if (tag !== "input" && tag !== "textarea") {
      return false;
    }
    const descriptor = [
      element.getAttribute("type"),
      element.getAttribute("autocomplete"),
      element.getAttribute("name"),
      element.getAttribute("id"),
      element.getAttribute("placeholder"),
      element.getAttribute("aria-label")
    ].join(" ");
    return /password|email|tel|phone|cc-|card|token|secret|api|otp/i.test(descriptor);
  }

  async function executeCommand(command) {
    switch (command?.action) {
      case "click":
        return click(command.element_id);
      case "type":
        return typeInto(command.element_id, command.text || "");
      case "scroll":
        window.scrollBy({ left: command.deltaX || 0, top: command.deltaY || 500, behavior: "smooth" });
        return { action: "scroll" };
      case "navigate":
        location.href = command.url;
        return { action: "navigate" };
      case "go_back":
        history.back();
        return { action: "go_back" };
      case "press_key":
        document.activeElement?.dispatchEvent(new KeyboardEvent("keydown", { key: command.key, bubbles: true }));
        return { action: "press_key" };
      default:
        throw new Error(`Unsupported command: ${command?.action}`);
    }
  }

  function click(elementId) {
    const target = findElement(elementId);
    if (!target) {
      throw new Error(`Element not found: ${elementId}`);
    }
    
    // Smooth scroll into view
    target.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });

    // Visual pulse effect
    target.classList.remove("fable-agent-active-target");
    void target.offsetWidth; // trigger reflow
    target.classList.add("fable-agent-active-target");

    setTimeout(() => {
      target.focus?.({ preventScroll: true });
      
      // Dispatch full mouse click event sequence
      target.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true, view: window }));
      target.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true, view: window }));
      target.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
      
      // Call native click() if button/link/input
      if (typeof target.click === "function") {
        target.click();
      }
    }, 200);

    return { action: "click", element_id: elementId, tag: target.tagName.toLowerCase() };
  }

  function typeInto(elementId, text) {
    const target = findElement(elementId);
    if (!target) {
      throw new Error(`Element not found: ${elementId}`);
    }
    target.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
    target.classList.add("fable-agent-active-target");
    target.focus();

    if (target.isContentEditable) {
      document.execCommand("insertText", false, text);
    } else {
      target.value = text;
      target.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: text }));
      target.dispatchEvent(new Event("change", { bubbles: true }));
    }
    return { action: "type", element_id: elementId, characters: text.length };
  }

  function findElement(elementId) {
    if (!elementId) return null;

    // 1. By exact data-privacy-agent-id
    let el = document.querySelector(`[data-privacy-agent-id="${CSS.escape(elementId)}"]`);
    if (el) return el;

    // 2. By standard DOM ID attribute
    el = document.getElementById(elementId);
    if (el) return el;

    // 3. By selector
    try {
      el = document.querySelector(`#${CSS.escape(elementId)}`);
      if (el) return el;
    } catch (_) {}

    // 4. By name attribute
    el = document.querySelector(`[name="${CSS.escape(elementId)}"]`);
    if (el) return el;

    // 5. Fuzzy match on text / aria-label for buttons
    const buttons = Array.from(document.querySelectorAll("button, [role='button'], a, input[type='button'], input[type='submit']"));
    const wanted = elementId.toLowerCase().replace(/[^a-z0-9]/g, "");
    for (const btn of buttons) {
      const text = (btn.textContent || btn.value || btn.getAttribute("aria-label") || "").toLowerCase().replace(/[^a-z0-9]/g, "");
      if (text && (text.includes(wanted) || wanted.includes(text))) {
        return btn;
      }
    }

    return null;
  }

  function stableId(element, index) {
    if (element.id) {
      return element.id;
    }
    if (element.dataset.privacyAgentId) {
      return element.dataset.privacyAgentId;
    }
    const label = [
      element.getAttribute("id"),
      element.getAttribute("name"),
      element.getAttribute("aria-label"),
      safeText(element)
    ]
      .filter(Boolean)
      .join("-")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_|_$/g, "")
      .slice(0, 48);
    return `${label || element.tagName.toLowerCase()}_${index + 1}`;
  }

  function safeText(element) {
    if ("value" in element && element.type === "password") {
      return "";
    }
    return visibleText(element).slice(0, 200);
  }

  function visibleText(element) {
    if (!element) {
      return "";
    }
    return String(element.innerText || element.textContent || "").replace(/\s+/g, " ").trim();
  }

  function isVisible(element) {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  }
})();
