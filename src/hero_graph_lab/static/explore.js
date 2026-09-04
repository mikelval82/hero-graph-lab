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
  agentMode: "auto",
  streamingText: "",
  eventCursor: 0,
};

let exploreSessionPromise = null;

function activateInspectorTab(name) {
  if (name !== "chat") return;
  document.querySelector("#chat-panel")?.removeAttribute("hidden");
  document.querySelectorAll("[data-inspector-tab]").forEach((tab) => {
    tab.setAttribute("aria-selected", String(tab.dataset.inspectorTab === "chat"));
  });
}

let mcpProposalPollPending = false;
let mcpProposalPollTimer = null;

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

function proposalNeedsObservedGraphRefresh(action) {
  if (action?.op === "add_node") return Boolean(action.parent_id) && !graphNode(action.parent_id);
  if (action?.op !== "add_relation") return false;
  return !graphNode(action.source_id) || !graphNode(action.target_id);
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
    let refreshedObservedGraph = false;
    for (const item of inbox.items || []) {
      let result = globalThis.applyAgentGraphProposals([item.action]);
      if (
        result.rejected
        && !refreshedObservedGraph
        && proposalNeedsObservedGraphRefresh(item.action)
      ) {
        await loadExperiment({ restoreLocalDesign: true });
        refreshedObservedGraph = true;
        result = globalThis.applyAgentGraphProposals([item.action]);
      }
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

function scheduleMcpProposalPoll() {
  clearTimeout(mcpProposalPollTimer);
  mcpProposalPollTimer = setTimeout(async () => {
    if (document.visibilityState !== "hidden") await pollMcpProposals();
    scheduleMcpProposalPoll();
  }, 2500);
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
    proposalNodes: state.graph ? state.graph.nodes.filter((node) => node.status === "proposed").map((node) => ({
      id: node.id,
      label: node.label,
      kind: node.kind,
      parent: node.parent || null,
      description: node.designDescription || "",
      target_path: node.target_path || "",
      qualified_name: node.qualified_name || "",
      signature: node.signature || "",
      docstring: node.docstring || "",
      satisfies: node.satisfies || [],
      acceptance: node.acceptance || [],
    })) : [],
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
  const heading = document.createElement("div");
  heading.className = "chat-message-heading";
  const header = document.createElement("span");
  header.textContent = message.role === "user" ? "YOU" : "CODEX";
  heading.append(header);
  if (message.role !== "user") heading.append(globalThis.createChatCopyButton(message.content));
  const body = document.createElement(message.role === "user" ? "p" : "div");
  body.className = message.role === "user" ? "" : "chat-message-body rich-content";
  if (message.role === "user") body.textContent = message.content;
  else globalThis.RichContentRenderer.render(body, message.content, { prefix: "explore-mermaid" });
  article.append(heading, body);
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
  const messages = document.querySelector("#chat-messages");
  const liveStatus = document.querySelector("#chat-status");
  messages.replaceChildren();
  exploreState.messages.forEach((message) => appendExploreMessage(messages, message));
  if (!exploreState.messages.length) {
    const empty = document.createElement("p");
    empty.className = "empty-list";
    empty.textContent = "Select code or graph nodes, then ask how they work or relate.";
    messages.append(empty);
  }
  if (exploreState.streamingText) {
    appendExploreMessage(messages, { role: "assistant", content: exploreState.streamingText });
  }
  if (liveStatus) messages.append(liveStatus);
  messages.scrollTop = messages.scrollHeight;
  document.querySelector("#chat-phase").textContent = exploreState.provider
    ? `${exploreState.provider === "codex" ? "Codex" : exploreState.provider} / ${exploreState.model}`
    : "Unavailable";
  document.querySelector("#chat-input-label").textContent = "Ask Codex";
  document.querySelector("#chat-input").placeholder = "Ask about the code, propose a design, or request implementation";
  // Session creation is lazy as well as eager: the user must be able to
  // submit even if the initial background request is still starting/fails.
  // submitExplorePrompt() creates the session before posting the message.
  document.querySelector("#chat-input").disabled = exploreState.pending;
  document.querySelector("#chat-form button[type='submit']").disabled = exploreState.pending;
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

function startExploreSession() {
  if (exploreState.sessionId) return Promise.resolve(exploreState.sessionId);
  if (exploreSessionPromise) return exploreSessionPromise;
  exploreState.starting = true;
  updateExploreBusyState();
  if (document.body.dataset.chatMode === "explore") {
    document.querySelector("#chat-phase").textContent = "Connecting";
  }
  exploreSessionPromise = (async () => {
    try {
      const session = await exploreRequest("/sessions", { method: "POST", headers: { "Content-Length": "0" } });
      exploreState.sessionId = session.id;
      exploreState.eventCursor = 0;
      exploreState.provider = session.provider;
      exploreState.model = session.model;
      exploreState.messages = session.messages || [];
    } catch (error) {
      document.querySelector("#chat-status").textContent = error.message;
    } finally {
      exploreState.starting = false;
      updateExploreBusyState();
      renderExploreChat();
      dispatchEvent(new CustomEvent("explore-state-changed"));
      exploreSessionPromise = null;
    }
    return exploreState.sessionId;
  })();
  return exploreSessionPromise;
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
  document.querySelector("#chat-status").textContent = exploreState.agentMode === "implement"
    ? "Implementing approved contract"
    : "Exploring";
  renderExploreChat();
  dispatchEvent(new CustomEvent("explore-state-changed"));
  let answer = null;
  let session = null;
  try {
    const designSync = await fetch("/api/mcp/design", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nodes: context.proposalNodes || [],
        edges: context.proposalEdges || [],
      }),
    });
    if (!designSync.ok) throw new Error("No se pudo sincronizar el diseño con Graph Lab");
    const result = await exploreRequest(`/sessions/${encodeURIComponent(exploreState.sessionId)}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: question, context }),
    });
    if (result.mode === "stream") {
      await streamExploreSession();
      session = await exploreRequest(`/sessions/${encodeURIComponent(exploreState.sessionId)}`);
      exploreState.messages = session.messages || [];
      exploreState.streamingText = "";
    } else {
      session = result.session || result;
      exploreState.messages = session.messages || [];
    }
    await refreshContractRealizations();
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

async function refreshContractRealizations() {
  const response = await fetch("/api/contracts", { headers: { Accept: "application/json" } });
  if (!response.ok || !state.graph) return;
  const payload = await response.json();
  const realized = new Map();
  for (const contract of payload.contracts || []) {
    if (contract.status !== "MATERIALIZED") continue;
    const metadata = contract.metadata || {};
    const accepted = new Set(metadata.accepted_paths || []);
    for (const path of metadata.realized_paths || []) {
      realized.set(path, accepted.has(path) ? "accepted" : "materialized");
    }
  }
  if (!realized.size) return;
  const promoted = new Set();
  state.graph.nodes.forEach((node) => {
    const status = realized.get(node.target_path);
    if (!status || !["proposed", "modified"].includes(node.status)) return;
    const implementation = state.graph.nodes.find((candidate) => (
      ["observed", "accepted"].includes(candidate.status || "observed")
      && candidate.source === node.target_path
      && candidate.kind === node.kind
      && candidate.label === node.label
    ));
    node.status = status;
    node.realization = { status, contract: "codex", node_id: implementation?.id || null };
    if (implementation) {
      node.source = implementation.source;
      node.line = implementation.line;
      node.end_line = implementation.end_line;
    }
    promoted.add(node.id);
  });
  state.graph.edges.forEach((edge) => {
    if (!promoted.has(edge.source) && !promoted.has(edge.target)) return;
    if (["proposed", "modified"].includes(edge.status)) edge.status = "materialized";
  });
  saveDesign();
  render();
}

function streamExploreSession() {
  return new Promise((resolve, reject) => {
    const source = new EventSource(
      `/api/explore/sessions/${encodeURIComponent(exploreState.sessionId)}/events?after=${exploreState.eventCursor}`,
    );
    source.onmessage = (message) => {
      let event;
      try {
        event = JSON.parse(message.data);
      } catch (error) {
        return;
      }
      if (Number.isInteger(event.id)) exploreState.eventCursor = Math.max(exploreState.eventCursor, event.id);
      const data = event.data || {};
      if (event.type === "agent_message_delta") {
        const text = String(data.text || "").trim();
        if (text && !exploreState.streamingText.includes(text)) {
          exploreState.streamingText = exploreState.streamingText
            ? `${exploreState.streamingText}\n\n${text}`
            : text;
          renderExploreChat();
        }
      } else if (event.type === "tool_activity") {
        document.querySelector("#chat-status").textContent = `Codex: ${data.tool || "working"}`;
        renderExploreChat();
      } else if (event.type === "agent_started") {
        document.querySelector("#chat-status").textContent = data.message || "Codex está trabajando";
        renderExploreChat();
      } else if (event.type === "agent_progress") {
        document.querySelector("#chat-status").textContent = data.message || "Codex está trabajando";
        renderExploreChat();
      } else if (event.type === "agent_completed") {
        if (data.text) {
          exploreState.streamingText = String(data.text);
          renderExploreChat();
        }
        source.close();
        resolve();
      } else if (event.type === "agent_failed") {
        source.close();
        const error = data.error || "Codex failed";
        document.querySelector("#chat-status").textContent = error;
        renderExploreChat();
        reject(new Error(error));
      }
    };
    source.onerror = () => {
      source.close();
      reject(new Error("Codex event stream disconnected"));
    };
  });
}

document.querySelectorAll("[data-chat-mode]").forEach((button) => {
  button.addEventListener("click", () => {
    setChatMode(button.dataset.chatMode);
    if (button.dataset.chatMode === "explore" && !exploreState.sessionId) startExploreSession();
  });
});
async function selectExploreAgentMode(button) {
  const requested = button.dataset.exploreAgentMode;
  if (requested === "implement") {
    try {
      const response = await fetch("/api/harness/v1/contracts/tasks", { headers: { Accept: "application/json" } });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.message || payload.detail || "HARNESS is not ready");
      const pending = (payload.tasks || []).filter((task) => task.status === "pending");
      if (!pending.length) throw new Error("Implement requires an approved pending task contract");
      const competing = pending.find((task) => task.execution?.status === "active" && task.execution.actor !== "chat");
      if (competing) throw new Error(`Execution is owned by ${competing.execution.actor}`);
    } catch (error) {
      document.querySelector("#chat-status").textContent = error.message;
      return;
    }
  }
  exploreState.agentMode = requested;
  document.querySelectorAll("[data-explore-agent-mode]").forEach((candidate) => {
    candidate.setAttribute("aria-pressed", String(candidate === button));
  });
  document.querySelector("#chat-status").textContent = requested === "implement"
    ? "Implement mode ready: HARNESS will enforce the approved contract"
    : "";
  renderExploreChat();
}

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
document.querySelector("#chat-input").addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  document.querySelector("#chat-form").requestSubmit();
});
document.querySelector("#chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = document.querySelector("#chat-input");
  const text = input.value.trim();
  if (!text || exploreState.pending) return;
  input.value = "";
  exploreState.messages.push({ role: "user", content: text });
  renderExploreChat();
  await submitExplorePrompt(text);
});
addEventListener("graph-selection-changed", updateExploreContext);
addEventListener("graph-experiment-ready", updateExploreContext);
addEventListener("graph-experiment-ready", pollMcpProposals);

startExploreSession();
scheduleMcpProposalPoll();
