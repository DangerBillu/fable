const startButton = document.getElementById("start");
const stopButton = document.getElementById("stop");
const goalInput = document.getElementById("goal");

startButton.addEventListener("click", async () => {
  await chrome.runtime.sendMessage({ type: "START_AGENT", goal: goalInput.value });
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
    document.getElementById(id).textContent = String(stats[id] || 0);
  }
}

setInterval(refresh, 1000);
refresh();

