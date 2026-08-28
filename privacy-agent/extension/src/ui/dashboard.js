const startButton = document.getElementById("start");
const stopButton = document.getElementById("stop");
const goalInput = document.getElementById("goal");

window.setGoal = function(goalText) {
  if (goalInput) {
    goalInput.value = goalText;
  }
};

startButton.addEventListener("click", async () => {
  const goal = goalInput.value.trim();
  if (!goal) {
    goalInput.focus();
    return;
  }
  startButton.disabled = true;
  await chrome.runtime.sendMessage({ type: "START_AGENT", goal });
  startButton.disabled = false;
  refresh();
});

stopButton.addEventListener("click", async () => {
  await chrome.runtime.sendMessage({ type: "STOP_AGENT" });
  refresh();
});

async function refresh() {
  const response = await chrome.runtime.sendMessage({ type: "GET_STATUS" });
  if (!response?.ok) {
    return;
  }
  const stats = response.stats;
  document.getElementById("status").textContent = response.running ? "Running" : stats.status;
  for (const id of ["screenshots", "facesBlurred", "redacted", "tokenized", "blocked", "approved"]) {
    const el = document.getElementById(id);
    if (el) {
      el.textContent = String(stats[id] || 0);
    }
  }
}

setInterval(refresh, 1000);
refresh();
