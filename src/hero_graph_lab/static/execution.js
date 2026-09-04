async function refreshExecutionSurface() {
  const stage = document.querySelector("#mission-stage-label");
  const branch = document.querySelector("#mission-branch-label");
  const summary = document.querySelector("#mission-summary");
  const actions = document.querySelector("#mission-actions");
  try {
    const response = await fetch("/api/capabilities", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Capabilities request failed (${response.status})`);
    const payload = await response.json();
    const agent = payload.agent || {};
    stage.textContent = "Local design";
    branch.textContent = `${agent.provider === "codex" ? "Codex" : agent.provider || "Codex"} · ${agent.model || "CLI"}`;
    summary.textContent = "Codex reads first, proposes design changes for review, and implements only after an approved contract exists.";
    actions.replaceChildren();
  } catch (error) {
    stage.textContent = "Unavailable";
    branch.textContent = "Graph Lab API unreachable";
    summary.textContent = error.message;
  }
}

refreshExecutionSurface();
