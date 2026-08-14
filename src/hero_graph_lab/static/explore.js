const exploreState = {
  sessionId: null,
  messages: [],
  provider: null,
  model: null,
  pending: false,
  starting: false,
  pinnedNodeIds: new Set(),
  listening: false,
  speakResponses: false,
  voiceInputBase: "",
  agentMode: "read",
};

let mcpProposalPollPending = false;

document.body.dataset.chatMode = "explore";
const BrowserSpeechRecognition = globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition;
const voiceRecognition = BrowserSpeechRecognition ? new BrowserSpeechRecognition() : null;

if (voiceRecognition) {
  voiceRecognition.continuous = false;
  voiceRecognition.interimResults = true;
  voiceRecognition.lang = navigator.language || "en-US";
  voiceRecognition.addEventListener("start", () => {
    exploreState.listening = true;
    exploreState.voiceInputBase = document.querySelector("#chat-input").value.trim();
    document.querySelector("#chat-status").textContent = "Listening";
    renderExploreVoiceControls();
  });
  voiceRecognition.addEventListener("result", (event) => {
    const transcript = [...event.results].map((result) => result[0].transcript).join(" ").trim();
    document.querySelector("#chat-input").value = [exploreState.voiceInputBase, transcript].filter(Boolean).join(" ");
  });
  voiceRecognition.addEventListener("error", (event) => {
    document.querySelector("#chat-status").textContent = event.error === "not-allowed"
      ? "Microphone permission denied"
      : `Voice input failed: ${event.error}`;
  });
  voiceRecognition.addEventListener("end", () => {
    exploreState.listening = false;
    if (document.querySelector("#chat-status").textContent === "Listening") {
      document.querySelector("#chat-status").textContent = "Voice input ready";
    }
    renderExploreVoiceControls();
  });
}

async function exploreRequest(path, options = {}) {
  const response = await fetch(`/api/explore${path}`, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `Explore request failed (${response.status})`);
  return payload;
}

async function pollMcpProposals() {
  if (mcpProposalPollPending || !state.graph || typeof globalThis.applyAgentGraphProposals !== "function") return;
  mcpProposalPollPending = true;
  try {
    const response = await fetch("/api/mcp/proposals", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`MCP proposal inbox failed (${response.status})`);
    const inbox = await response.json();
    const revisions = [];
    const totals = { nodes: 0, relations: 0, replayed: 0 };
    for (const item of inbox.items || []) {
      const result = globalThis.applyAgentGraphProposals([item.action]);
      if (result.rejected) continue;
      revisions.push(item.revision);
      totals.nodes += result.nodes;
      totals.relations += result.relations;
      totals.replayed += result.replayed || 0;
    }
    if (!revisions.length) return;
    const acknowledged = await fetch("/api/mcp/proposals/ack", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ revisions }),
    });
    if (!acknowledged.ok) throw new Error(`MCP proposal acknowledgement failed (${acknowledged.status})`);
    const added = totals.nodes + totals.relations;
    if (added) {
      document.querySelector("#chat-status").textContent = `${totals.nodes} node and ${totals.relations} relationship proposal${added === 1 ? "" : "s"} received from Codex MCP and added to the local draft.`;
    }
  } catch (error) {
    console.warn("Graph Lab MCP proposal polling failed", error);
  } finally {
    mcpProposalPollPending = false;
  }
}

function updateExploreBusyState() {
  const busy = exploreState.starting || exploreState.pending;
  document.body.classList.toggle("model-pending", busy);
  document.body.setAttribute("aria-busy", String(busy));
}

function currentExploreContext() {
  const selected = graphNode(state.selected);
  const visibleSource = selected?.source
    ? { path: selected.source, startLine: selected.line || 1, endLine: selected.end_line || selected.line || 1 }
    : null;
  return {
    assistantMode: exploreState.agentMode,
    selectedNodeId: selected?.id || null,
    selectedRelationId: state.selectedRelation || null,
    scopeId: state.scope || null,
    visibleNodeIds: state.graph ? navigationGraph().nodes.map((node) => node.id) : [],
    pinnedNodeIds: [...exploreState.pinnedNodeIds],
    proposalNodes: state.graph ? state.graph.nodes.filter((node) => node.status === "proposed").map((node) => ({ id: node.id, label: node.label, kind: node.kind, parent: node.parent || null })) : [],
    proposalEdges: state.graph ? state.graph.edges.filter((edge) => edge.status === "proposed").map((edge) => ({ id: edge.id, source: edge.source, target: edge.target, kind: edge.kind, label: edge.label || "" })) : [],
    visibleSource,
  };
}

function renderPinnedNodes() {
  const list = document.querySelector("#explore-pins");
  list.replaceChildren();
  [...exploreState.pinnedNodeIds].forEach((nodeId) => {
    const node = graphNode(nodeId);
    if (!node) {
      exploreState.pinnedNodeIds.delete(nodeId);
      return;
    }
    const item = document.createElement("li");
    const details = document.createElement("span");
    const name = document.createElement("strong");
    name.textContent = `${node.kind} / ${node.label}`;
    const source = document.createElement("small");
    source.textContent = node.source ? `${node.source}:${node.line || 1}` : "Graph metadata";
    details.append(name, source);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.dataset.unpinNode = node.id;
    remove.setAttribute("aria-label", `Unpin ${node.label}`);
    remove.title = `Unpin ${node.label}`;
    remove.textContent = "x";
    item.append(details, remove);
    list.append(item);
  });
  list.hidden = !list.children.length;
}

function updateExploreContext() {
  const selected = graphNode(state.selected);
  renderPinnedNodes();
  const pins = exploreState.pinnedNodeIds.size;
  const current = selected ? `${selected.kind} / ${selected.label}` : state.selectedRelation ? "Selected relationship" : "No graph selection";
  document.querySelector("#explore-context-label").textContent = `${current}${pins ? ` / ${pins} pinned` : ""}`;
  document.querySelector("#explore-pin").disabled = !selected;
  document.querySelector("#explore-pin").textContent = selected && exploreState.pinnedNodeIds.has(selected.id) ? "Unpin" : "Pin";
  document.querySelector("#explore-clear-pins").disabled = !pins;
}

function appendExploreMessage(container, message) {
  const article = document.createElement("article");
  article.className = `chat-message ${message.role === "user" ? "human" : "agent"}`;
  const header = document.createElement("span");
  header.textContent = message.role === "user" ? "YOU / EXPLORE" : `${exploreState.provider.toUpperCase()} / ${exploreState.model}`;
  const body = document.createElement(message.role === "user" ? "p" : "div");
  body.className = message.role === "user" ? "" : "chat-message-body rich-content";
  if (message.role === "user") body.textContent = message.content;
  else globalThis.RichContentRenderer.render(body, message.content, { prefix: "explore-mermaid" });
  article.append(header, body);
  container.append(article);
}

function renderExploreVoiceControls() {
  const microphone = document.querySelector("#chat-microphone");
  const speech = document.querySelector("#chat-speech");
  microphone.hidden = false;
  speech.hidden = false;
  microphone.disabled = !voiceRecognition || !exploreState.sessionId || exploreState.pending;
  microphone.setAttribute("aria-pressed", String(exploreState.listening));
  microphone.textContent = exploreState.listening ? "Stop" : "Mic";
  if (!voiceRecognition) microphone.title = "Voice input is not supported by this browser";
  speech.disabled = !("speechSynthesis" in globalThis);
  speech.setAttribute("aria-pressed", String(exploreState.speakResponses));
  speech.textContent = exploreState.speakResponses ? "Mute" : "Read";
}

function stopExploreVoice() {
  if (exploreState.listening) voiceRecognition?.stop();
  globalThis.speechSynthesis?.cancel();
}

function speakExploreResponse(message) {
  if (!exploreState.speakResponses || !message || !("speechSynthesis" in globalThis)) return;
  const utterance = new SpeechSynthesisUtterance(message.content);
  utterance.lang = navigator.language || "en-US";
  globalThis.speechSynthesis.cancel();
  globalThis.speechSynthesis.speak(utterance);
}

function latestAssistantMessage() {
  for (let index = exploreState.messages.length - 1; index >= 0; index -= 1) {
    if (exploreState.messages[index].role === "assistant") return exploreState.messages[index];
  }
  return null;
}

function renderExploreChat() {
  if (document.body.dataset.chatMode !== "explore") return;
  const messages = document.querySelector("#chat-messages");
  messages.replaceChildren();
  exploreState.messages.forEach((message) => appendExploreMessage(messages, message));
  if (!exploreState.messages.length) {
    const empty = document.createElement("p");
    empty.className = "empty-list";
    empty.textContent = "Select code or graph nodes, then ask how they work or relate.";
    messages.append(empty);
  }
  messages.scrollTop = messages.scrollHeight;
  document.querySelector("#chat-phase").textContent = exploreState.provider
    ? `${exploreState.provider} / ${exploreState.model}`
    : "Unavailable";
  document.querySelector("#chat-input-label").textContent = exploreState.agentMode === "propose" ? "Ask or propose graph changes" : "Ask about this code";
  document.querySelector("#chat-input").placeholder = exploreState.agentMode === "propose" ? "Describe nodes or relationships to propose" : "Ask about the selected code or graph";
  document.querySelector("#chat-input").disabled = !exploreState.sessionId || exploreState.pending;
  document.querySelector("#chat-form button[type='submit']").disabled = !exploreState.sessionId || exploreState.pending;
  document.querySelector("#chat-done").hidden = true;
  document.querySelector("#explore-context").hidden = false;
  renderExploreVoiceControls();
  const count = document.querySelector("#chat-count");
  count.textContent = exploreState.messages.length;
  count.hidden = !exploreState.messages.length;
  updateExploreContext();
}

function setChatMode(mode) {
  if (mode !== "explore") stopExploreVoice();
  document.body.dataset.chatMode = mode;
  document.querySelectorAll("[data-chat-mode]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.chatMode === mode));
  });
  if (mode === "explore") renderExploreChat();
  else renderChat();
}

async function startExploreSession() {
  if (exploreState.starting || exploreState.sessionId) return;
  exploreState.starting = true;
  updateExploreBusyState();
  if (document.body.dataset.chatMode === "explore") {
    document.querySelector("#chat-phase").textContent = "Connecting";
  }
  try {
    const session = await exploreRequest("/sessions", { method: "POST", headers: { "Content-Length": "0" } });
    exploreState.sessionId = session.id;
    exploreState.provider = session.provider;
    exploreState.model = session.model;
    exploreState.messages = session.messages || [];
  } catch (error) {
    document.querySelector("#chat-status").textContent = error.message;
  } finally {
    exploreState.starting = false;
    updateExploreBusyState();
  }
  renderExploreChat();
  dispatchEvent(new CustomEvent("explore-state-changed"));
}

function openExploreChat() {
  if (document.body.classList.contains("inspector-collapsed")) {
    globalThis.HeroPanelLayout.expand("inspector");
  }
  activateInspectorTab("chat");
  setChatMode("explore");
}

async function submitExplorePrompt(text, context = currentExploreContext()) {
  const question = text.trim();
  if (!question || exploreState.pending) return;
  openExploreChat();
  if (!exploreState.sessionId) await startExploreSession();
  if (!exploreState.sessionId) return;
  exploreState.pending = true;
  updateExploreBusyState();
  document.querySelector("#chat-status").textContent = "Exploring";
  renderExploreChat();
  dispatchEvent(new CustomEvent("explore-state-changed"));
  let answer = null;
  try {
    const session = await exploreRequest(`/sessions/${encodeURIComponent(exploreState.sessionId)}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: question, context }),
    });
    exploreState.messages = session.messages || [];
    const proposalResult = globalThis.applyAgentGraphProposals(session.actions || []);
    const proposalCount = proposalResult.nodes + proposalResult.relations;
    document.querySelector("#chat-status").textContent = proposalCount
      ? `${proposalResult.nodes} node and ${proposalResult.relations} relationship proposal${proposalCount === 1 ? "" : "s"} added to the local draft${proposalResult.rejected ? `; ${proposalResult.rejected} rejected` : ""}.`
      : proposalResult.rejected ? `${proposalResult.rejected} invalid graph proposal${proposalResult.rejected === 1 ? " was" : "s were"} rejected.` : "";
    answer = latestAssistantMessage();
    speakExploreResponse(answer);
  } catch (error) {
    document.querySelector("#chat-status").textContent = error.message;
  } finally {
    exploreState.pending = false;
    updateExploreBusyState();
    renderExploreChat();
    dispatchEvent(new CustomEvent("explore-state-changed"));
  }
  return answer?.content || null;
}

document.querySelectorAll("[data-chat-mode]").forEach((button) => {
  button.addEventListener("click", () => {
    setChatMode(button.dataset.chatMode);
    if (button.dataset.chatMode === "explore" && !exploreState.sessionId) startExploreSession();
  });
});
document.querySelectorAll("[data-explore-agent-mode]").forEach((button) => {
  button.addEventListener("click", () => {
    exploreState.agentMode = button.dataset.exploreAgentMode;
    document.querySelectorAll("[data-explore-agent-mode]").forEach((candidate) => candidate.setAttribute("aria-pressed", String(candidate === button)));
    renderExploreChat();
  });
});
addEventListener("explore-chat-required", () => setChatMode("explore"));
document.querySelector("#explore-clear-pins").addEventListener("click", () => {
  exploreState.pinnedNodeIds.clear();
  updateExploreContext();
});
document.querySelector("#explore-pins").addEventListener("click", (event) => {
  const button = event.target.closest("[data-unpin-node]");
  if (!button) return;
  exploreState.pinnedNodeIds.delete(button.dataset.unpinNode);
  updateExploreContext();
});
document.querySelector("#chat-microphone").addEventListener("click", () => {
  if (!voiceRecognition) return;
  if (exploreState.listening) voiceRecognition.stop();
  else {
    try {
      voiceRecognition.start();
    } catch (error) {
      document.querySelector("#chat-status").textContent = error.message;
    }
  }
});
document.querySelector("#chat-speech").addEventListener("click", () => {
  exploreState.speakResponses = !exploreState.speakResponses;
  if (exploreState.speakResponses) speakExploreResponse(latestAssistantMessage());
  else globalThis.speechSynthesis?.cancel();
  renderExploreVoiceControls();
});
document.querySelector("#chat-form").addEventListener("submit", async (event) => {
  if (document.body.dataset.chatMode !== "explore") return;
  event.preventDefault();
  const input = document.querySelector("#chat-input");
  const text = input.value.trim();
  if (!text || !exploreState.sessionId || exploreState.pending) return;
  input.value = "";
  await submitExplorePrompt(text);
});
addEventListener("graph-selection-changed", updateExploreContext);
addEventListener("graph-experiment-ready", updateExploreContext);
addEventListener("graph-experiment-ready", pollMcpProposals);

startExploreSession();
setInterval(pollMcpProposals, 1000);
