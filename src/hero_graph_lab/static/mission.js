const missionState = {
  host: null,
  capabilities: null,
  snapshot: null,
  design: null,
  messages: [],
  operation: null,
  activity: [],
  contracts: [],
  selectedDocument: null,
  documentRevision: 0,
  documentMode: "preview",
  designDirty: false,
  localDraft: null,
  localBaseGraph: null,
  canonicalGraph: null,
  graphReady: false,
  observedRevision: null,
  mergedDesignFingerprint: null,
  eventCursor: 0,
  eventLoopRunning: false,
  refreshTimer: null,
};

const missionDialog = document.querySelector("#mission-dialog");
const missionForm = document.querySelector("#mission-form");
const projectDialog = document.querySelector("#project-dialog");
const projectForm = document.querySelector("#project-form");
const documentEditor = document.querySelector("#document-editor");
const codeContent = document.querySelector("#code-content");
const codeEmpty = document.querySelector("#code-empty");

const documentLabels = {
  "mission/idea": "Idea",
  "mission/brainstorm": "Research",
  "mission/brief": "Brief",
  "mission/tasks": "Workplan",
  "mission/report": "Mission report",
  spec: "Specification",
  plan: "Plan",
  decisions: "Decisions",
  status: "Implementation status",
  audit: "Review",
  reconciliation: "Reconciliation",
  contract: "Task contract",
  verification: "Contract verification",
};
const processDocumentOrder = ["mission/idea", "mission/brainstorm", "mission/brief", "mission/tasks", "mission/report"];
const taskDocumentOrder = ["contract", "spec", "plan", "decisions", "status", "audit", "verification", "reconciliation"];

const actionDefinitions = {
  run_research: { endpoint: "research", label: "Run research" },
  start_grill: { endpoint: "grill", label: "Start grill" },
  skip_grill: { endpoint: "skip-grill", label: "Continue without Grill" },
  approve_design: { endpoint: "approve-design", label: "Approve design" },
  approve_execution: { endpoint: "approve-execution", label: "Approve execution" },
  request_amendment: { endpoint: "request-amendment", label: "Request amendment" },
  prepare_task: { endpoint: "prepare-task", label: "Prepare next task" },
  approve_task: { endpoint: "execute-task", label: "Approve and execute" },
  retry: { endpoint: "retry-review", label: "Retry" },
};

async function jsonRequest(path, options = {}) {
  const response = await fetch(path, options);
  const text = await response.text();
  let payload = {};
  if (text) {
    try { payload = JSON.parse(text); } catch (error) { payload = { detail: text }; }
  }
  if (!response.ok) {
    const failure = new Error(payload.message || payload.detail || payload.error || `Request failed (${response.status})`);
    failure.status = response.status;
    failure.payload = payload;
    throw failure;
  }
  return payload;
}

function harnessRequest(path, options = {}) {
  return jsonRequest(`/api/harness${path}`, options);
}

function jsonOptions(method, body) {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

function readable(value) {
  return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function compactNumber(value) {
  const number = Number(value || 0);
  return new Intl.NumberFormat("en", {
    notation: number >= 1000 ? "compact" : "standard",
    maximumFractionDigits: 1,
  }).format(number);
}

function activityMetrics(payload, { includeLimit = false } = {}) {
  if (payload.turn === undefined && payload.turns === undefined) return "";
  const turns = payload.turn ?? payload.turns;
  const turnLabel = includeLimit && payload.max_turns
    ? `${turns}/${payload.max_turns} turns`
    : `${turns} turns`;
  return `${turnLabel} · ${compactNumber(payload.input_tokens)} in · ${compactNumber(payload.output_tokens)} out`;
}

function activateInspectorTab(name) {
  document.querySelectorAll("[data-inspector-tab]").forEach((button) => {
    const selected = button.dataset.inspectorTab === name;
    button.setAttribute("aria-selected", String(selected));
    document.querySelector(`#${button.dataset.inspectorTab}-panel`).hidden = !selected;
  });
}

function renderHostStatus() {
  const running = Boolean(missionState.host?.running);
  const indicator = document.querySelector("#harness-indicator");
  const missionChatButton = document.querySelector('[data-chat-mode="mission"]');
  indicator.classList.toggle("online", running);
  missionChatButton.disabled = !running;
  missionChatButton.title = running ? "Mission conversation" : "Start a mission to enable Mission chat";
  if (!running && document.body.dataset.chatMode === "mission") {
    dispatchEvent(new CustomEvent("explore-chat-required"));
  }
  document.querySelector("#mission-launch").textContent = running ? "Open mission" : "Start mission";
  document.querySelector("#mission-project").value = missionState.host?.project_selected
    ? missionState.host.project_dir || ""
    : "";
  document.querySelector("#mission-stop").hidden = !running;
  if (!running) {
    missionState.capabilities = null;
    document.querySelector("#mission-stage-label").textContent = "Local design";
    document.querySelector("#mission-branch-label").textContent = missionState.host?.configured === false ? "HARNESS unavailable" : "HARNESS offline";
    document.querySelector("#mission-stage").textContent = "Offline";
    document.querySelector("#mission-summary").textContent = "Start a mission to bind this workspace to HARNESS.";
    document.querySelector("#mission-actions").replaceChildren();
    document.querySelector("#mission-documents").replaceChildren();
    document.querySelector("#mission-tasks").replaceChildren();
    document.querySelector("#mission-contracts").replaceChildren();
    document.querySelector("#mission-contract-section").hidden = true;
    missionState.activity = [];
    renderActivity();
  }
}

function renderMission() {
  renderHostStatus();
  const snapshot = missionState.snapshot;
  if (!snapshot) return;
  const mission = snapshot.mission;
  document.querySelector("#mission-stage-label").textContent = readable(mission.stage);
  document.querySelector("#mission-branch-label").textContent = `${mission.project_name} / ${mission.branch}`;
  document.querySelector("#mission-stage").textContent = readable(mission.stage);
  document.querySelector("#mission-summary").textContent = mission.blocked_reason || `${mission.mode.toUpperCase()} / session revision ${mission.revision}`;
  renderOperation();
  renderActivity();
  renderActions();
  renderDocuments();
  renderTasks();
  renderContracts();
  renderChat();
}

function renderOperation() {
  const element = document.querySelector("#mission-operation");
  const operation = missionState.operation;
  element.hidden = !operation;
  if (!operation) return;
  element.className = `mission-operation ${operation.status}`;
  const detail = operation.detail || operation.error || "";
  element.textContent = `${readable(operation.action)} / ${readable(operation.status)}${detail ? ` / ${detail}` : ""}`;
}

function activityDescription(event) {
  const payload = event.payload || {};
  const descriptions = {
    operation_started: () => `${readable(payload.action)} requested`,
    operation_finished: () => `${readable(payload.action)} ${readable(payload.status)}`,
    phase_started: () => `${readable(payload.phase)} started${payload.max_turns ? ` · limit ${payload.max_turns} turns` : ""}`,
    agent_progress: () => `${readable(payload.phase)} · ${activityMetrics(payload, { includeLimit: true })}`,
    phase_ended: () => payload.outcome === "completed"
      ? `${readable(payload.phase)} completed · ${activityMetrics(payload)} · ${payload.elapsed_seconds ?? "?"}s`
      : `${readable(payload.phase)} blocked · ${readable(payload.block_kind)}${activityMetrics(payload) ? ` · ${activityMetrics(payload)}` : ""}`,
    tool_call: () => payload.summary || readable(payload.tool),
    document_version_created: () => `${documentLabel(payload.logical_id)} saved · revision ${payload.revision}`,
    design_changed: () => `Design map ${readable(payload.status)} · revision ${payload.design_revision}`,
    design_approved: () => `Design approved · revision ${payload.design_revision}`,
    task_prepared: () => `${payload.task_id} ready for review`,
    task_completed: () => `${payload.task_id} completed`,
    execution_paused_for_amendment: () => "Execution paused for design review",
    mission_finalized: () => `Mission ${readable(payload.outcome)}`,
  };
  return descriptions[event.kind]?.() || null;
}

function recordActivity(events) {
  events.forEach((event) => {
    const description = activityDescription(event);
    if (!description) return;
    const item = {
      id: event.event_id,
      timestamp: event.timestamp,
      kind: event.kind,
      phase: event.payload?.phase || "",
      description,
    };
    if (event.kind === "agent_progress") {
      const phaseStart = missionState.activity.findLastIndex((candidate) => candidate.kind === "phase_started" && candidate.phase === item.phase);
      const previous = missionState.activity.findLastIndex((candidate, index) => index > phaseStart && candidate.kind === "agent_progress" && candidate.phase === item.phase);
      if (previous >= 0) missionState.activity[previous] = item;
      else missionState.activity.push(item);
      return;
    }
    if (event.kind === "phase_ended") {
      const phaseStart = missionState.activity.findLastIndex((candidate) => candidate.kind === "phase_started" && candidate.phase === item.phase);
      const progress = missionState.activity.findLastIndex((candidate, index) => index > phaseStart && candidate.kind === "agent_progress" && candidate.phase === item.phase);
      if (progress >= 0) missionState.activity.splice(progress, 1);
    }
    missionState.activity.push(item);
  });
  missionState.activity = missionState.activity.slice(-60);
  renderActivity();
}

function renderActivity() {
  const section = document.querySelector("#mission-activity-section");
  const list = document.querySelector("#mission-activity");
  const running = missionState.operation?.status === "running";
  section.hidden = !missionState.activity.length && !running;
  list.replaceChildren();
  missionState.activity.slice(-12).forEach((item) => {
    const row = document.createElement("li");
    row.className = `activity-${item.kind}`;
    const time = document.createElement("time");
    time.dateTime = item.timestamp;
    time.textContent = item.timestamp?.slice(11, 19) || "";
    const text = document.createElement("span");
    text.textContent = item.description;
    row.append(time, text);
    list.append(row);
  });
  const stateLabel = document.querySelector("#mission-activity-state");
  stateLabel.className = running ? "working" : "";
  stateLabel.textContent = running ? "Working" : "Idle";
  list.scrollTop = list.scrollHeight;
}

function renderActions() {
  const container = document.querySelector("#mission-actions");
  container.replaceChildren();
  const allowed = missionState.snapshot?.mission.allowed_actions || [];
  const supported = new Set(missionState.capabilities?.actions || []);
  const running = missionState.operation?.status === "running";
  allowed.forEach((action) => {
    const definition = actionDefinitions[action];
    if (!definition || !supported.has(definition.endpoint)) return;
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = definition.label;
    button.disabled = running;
    button.addEventListener("click", () => submitMissionAction(action, definition));
    container.append(button);
  });
  if (!container.children.length) {
    const empty = document.createElement("p");
    empty.className = "empty-list";
    empty.textContent = running ? "Operation in progress" : "No gate is currently available";
    container.append(empty);
  }
}

function documentLabel(logicalId) {
  const kind = logicalId.split("/").at(-1);
  return documentLabels[logicalId] || documentLabels[kind] || readable(kind);
}

function appendDocumentButton(container, item) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "mission-list-item";
  button.classList.toggle("selected", missionState.selectedDocument === item.logical_id);
  const label = document.createElement("strong");
  label.textContent = documentLabel(item.logical_id);
  const metadata = document.createElement("span");
  metadata.textContent = `r${item.revision} / ${item.author || "draft"}`;
  button.append(label, metadata);
  button.addEventListener("click", () => openMissionDocument(item.logical_id));
  container.append(button);
}

function appendDocumentGroup(container, title, documents, taskId = "") {
  if (!documents.length) return;
  const section = document.createElement("section");
  section.className = "document-group";
  const heading = document.createElement("header");
  const label = document.createElement("h3");
  label.textContent = title;
  heading.append(label);
  if (taskId) {
    const identity = document.createElement("span");
    identity.textContent = taskId;
    heading.prepend(identity);
  }
  const list = document.createElement("div");
  list.className = "document-group-list";
  documents.forEach((item) => appendDocumentButton(list, item));
  section.append(heading, list);
  container.append(section);
}

function renderDocuments() {
  const container = document.querySelector("#mission-documents");
  container.replaceChildren();
  const documents = [...(missionState.snapshot?.documents || [])];
  if (!documents.some((item) => item.logical_id === "mission/idea")) {
    documents.unshift({ logical_id: "mission/idea", revision: 0, author: "HUMAN" });
  }
  const processDocuments = documents
    .filter((item) => !item.logical_id.startsWith("task/"))
    .sort((left, right) => processDocumentOrder.indexOf(left.logical_id) - processDocumentOrder.indexOf(right.logical_id));
  appendDocumentGroup(container, "Process documents", processDocuments);
  const taskDocuments = new Map();
  documents.filter((item) => item.logical_id.startsWith("task/")).forEach((item) => {
    const taskId = item.logical_id.split("/")[1];
    if (!taskDocuments.has(taskId)) taskDocuments.set(taskId, []);
    taskDocuments.get(taskId).push(item);
  });
  const tasks = missionState.snapshot?.tasks || [];
  const taskIds = [...taskDocuments.keys()].sort((left, right) => {
    const leftIndex = tasks.findIndex((task) => task.id === left);
    const rightIndex = tasks.findIndex((task) => task.id === right);
    return (leftIndex < 0 ? Number.MAX_SAFE_INTEGER : leftIndex) - (rightIndex < 0 ? Number.MAX_SAFE_INTEGER : rightIndex);
  });
  taskIds.forEach((taskId) => {
    const task = tasks.find((candidate) => candidate.id === taskId);
    const items = taskDocuments.get(taskId).sort((left, right) => {
      const leftKind = left.logical_id.split("/").at(-1);
      const rightKind = right.logical_id.split("/").at(-1);
      return taskDocumentOrder.indexOf(leftKind) - taskDocumentOrder.indexOf(rightKind);
    });
    appendDocumentGroup(container, task?.title || readable(taskId), items, taskId);
  });
}

function renderTasks() {
  const container = document.querySelector("#mission-tasks");
  container.replaceChildren();
  const tasks = missionState.snapshot?.tasks || [];
  tasks.forEach((task) => {
    const row = document.createElement("div");
    row.className = `task-row ${task.status}`;
    const identity = document.createElement("span");
    identity.textContent = `${task.id} / ${task.complexity}`;
    const title = document.createElement("strong");
    title.textContent = task.title;
    const status = document.createElement("i");
    status.textContent = readable(task.status);
    row.append(identity, title, status);
    container.append(row);
  });
  if (!tasks.length) {
    const empty = document.createElement("p");
    empty.className = "empty-list";
    empty.textContent = "Workplan not generated";
    container.append(empty);
  }
}

function contractPreview(contract) {
  const lines = [];
  (contract.nodes || []).forEach((node) => {
    const name = String(node.qualified_name || node.label || node.id || "unnamed").split(".").at(-1);
    const path = node.target_path || "no target path";
    lines.push(`# ${node.kind || "unknown"} · ${path}`);
    if (node.kind === "class") lines.push(`class ${name}:`);
    else if (["function", "method"].includes(node.kind)) {
      const signature = String(node.signature || "(...)");
      lines.push(`def ${name}${signature.startsWith("(") ? signature : `(${signature})`}:`);
    } else if (node.kind === "module" || node.kind === "package") {
      lines.push(`# ${name}`);
    }
    if (node.docstring) lines.push(`    """${node.docstring}"""`);
    (node.acceptance || []).forEach((item) => lines.push(`    # acceptance: ${item}`));
    lines.push("");
  });
  return lines.join("\n").trim() || "No structural declarations in this task contract.";
}

function renderContracts() {
  const section = document.querySelector("#mission-contract-section");
  const container = document.querySelector("#mission-contracts");
  container.replaceChildren();
  const contracts = missionState.contracts || [];
  section.hidden = !contracts.length;
  contracts.forEach((item) => {
    const contract = item.contract || {};
    const execution = item.execution;
    const verifier = execution?.verifier;
    const stateName = verifier?.passed
      ? "materialized"
      : verifier && verifier.passed === false
        ? "divergent"
        : "proposed";
    const card = document.createElement("article");
    card.className = `contract-card ${stateName}`;
    const heading = document.createElement("header");
    const title = document.createElement("strong");
    title.textContent = `${contract.task?.id || "Task"} / ${contract.task?.title || "Approved slice"}`;
    const stateBadge = document.createElement("span");
    stateBadge.className = "contract-state";
    stateBadge.textContent = stateName;
    heading.append(title, stateBadge);
    const metadata = document.createElement("p");
    const owner = execution?.status === "active" ? execution.actor : "unowned";
    metadata.textContent = `snapshot ${contract.snapshot_id || "?"} · design r${contract.design_revision ?? "?"} · owner ${owner} · verifier ${verifier ? (verifier.passed ? "passed" : `${verifier.failed_checks || 0} failed`) : "not run"}`;
    const advisory = (contract.relationships || []).filter((edge) => edge.verification_level === "advisory").length;
    if (advisory) {
      const advisoryBadge = document.createElement("span");
      advisoryBadge.className = "contract-advisory";
      advisoryBadge.textContent = `${advisory} advisory relationship${advisory === 1 ? "" : "s"}`;
      metadata.append(" ", advisoryBadge);
    }
    const preview = document.createElement("pre");
    preview.className = "contract-preview";
    preview.textContent = contractPreview(contract);
    card.append(heading, metadata, preview);
    container.append(card);
  });
}

function renderChat() {
  if (document.body.dataset.chatMode !== "mission") return;
  const messages = document.querySelector("#chat-messages");
  messages.replaceChildren();
  missionState.messages.forEach((message) => {
    const article = document.createElement("article");
    const role = message.role.toLowerCase();
    const visualRole = role === "human" || role === "user" ? "human" : role === "tool" ? "tool" : "agent";
    article.className = `chat-message ${visualRole}`;
    const heading = document.createElement("div");
    heading.className = "chat-message-heading";
    const header = document.createElement("span");
    header.textContent = `${message.role} / ${message.phase}`;
    heading.append(header);
    if (visualRole === "agent") heading.append(globalThis.createChatCopyButton(message.content));
    const body = document.createElement("p");
    body.textContent = message.content;
    article.append(heading, body);
    messages.append(article);
  });
  messages.scrollTop = messages.scrollHeight;
  const grillActive = missionState.snapshot?.mission.stage === "grilling" || (missionState.operation?.action === "grill" && missionState.operation.status === "running");
  document.querySelector("#chat-phase").textContent = grillActive ? "Live" : "Idle";
  document.querySelector("#chat-input-label").textContent = "Reply";
  document.querySelector("#chat-input").placeholder = "Answer the current question";
  document.querySelector("#chat-input").disabled = !grillActive;
  document.querySelector("#chat-form button[type='submit']").disabled = !grillActive;
  document.querySelector("#chat-done").disabled = !grillActive;
  document.querySelector("#chat-done").hidden = false;
  document.querySelector("#chat-microphone").hidden = true;
  document.querySelector("#chat-speech").hidden = true;
  document.querySelector("#explore-context").hidden = true;
  document.querySelector("#explore-agent-mode").hidden = true;
  const count = document.querySelector("#chat-count");
  count.textContent = missionState.messages.length;
  count.hidden = !missionState.messages.length;
}

async function refreshMission({ mergeGraph = true } = {}) {
  missionState.host = await harnessRequest("/status");
  if (!missionState.host.running) {
    missionState.snapshot = null;
    missionState.design = null;
    missionState.contracts = [];
    missionState.operation = null;
    missionState.observedRevision = null;
    missionState.mergedDesignFingerprint = null;
    renderHostStatus();
    return;
  }
  const [capabilities, snapshot, design, transcript, operation] = await Promise.all([
    harnessRequest("/v1/capabilities"),
    harnessRequest("/v1/snapshot"),
    harnessRequest("/v1/design"),
    harnessRequest("/v1/messages"),
    harnessRequest("/v1/operation"),
  ]);
  missionState.capabilities = capabilities;
  missionState.snapshot = snapshot;
  missionState.design = design;
  missionState.messages = transcript.messages || [];
  missionState.operation = operation.operation;
  const contractStages = new Set(["ready", "task_preparation", "task_review", "executing", "reconciling", "completed"]);
  const contractIndex = contractStages.has(snapshot.mission.stage)
    ? await harnessRequest("/v1/contracts/tasks")
    : { tasks: [] };
  missionState.contracts = await Promise.all(
    (contractIndex.tasks || []).map((task) =>
      harnessRequest(`/v1/contracts/tasks/${encodeURIComponent(task.id)}`).catch(() => null)
    )
  ).then((items) => items.filter(Boolean));
  renderMission();
  const observedRevision = Number(snapshot.design?.observed_revision || 0);
  if (missionState.observedRevision === null) {
    missionState.observedRevision = observedRevision;
  } else if (observedRevision !== missionState.observedRevision) {
    await loadExperiment({ restoreLocalDesign: false });
    missionState.observedRevision = observedRevision;
  }
  if (mergeGraph) mergeMissionDesign();
  startEventLoop();
}

function scheduleMissionRefresh() {
  clearTimeout(missionState.refreshTimer);
  missionState.refreshTimer = setTimeout(() => {
    refreshMission().catch((error) => showMissionError(error));
  }, 100);
}

async function startEventLoop() {
  if (missionState.eventLoopRunning || !missionState.host?.running) return;
  missionState.eventLoopRunning = true;
  try {
    while (missionState.host?.running) {
      const payload = await harnessRequest(`/v1/events?after=${missionState.eventCursor}&wait=5`);
      const events = payload.events || [];
      if (events.length) {
        missionState.eventCursor = events.at(-1).event_id;
        recordActivity(events);
        await refreshMission();
      } else {
        await refreshMission();
      }
    }
  } catch (error) {
    missionState.host = { ...(missionState.host || {}), running: false };
    renderHostStatus();
  } finally {
    missionState.eventLoopRunning = false;
  }
}

async function submitMissionAction(action, definition) {
  try {
    if (action === "approve_design" && missionState.designDirty) await synchronizeDesign();
    await refreshMission({ mergeGraph: false });
    const body = {
      command_id: crypto.randomUUID(),
      expected_session_revision: missionState.snapshot.mission.revision,
    };
    if (action === "approve_design") body.base_design_revision = missionState.design.design_revision;
    if (action === "approve_task") body.task_id = missionState.snapshot.mission.active_task_id;
    const retryingPreparation = action === "retry"
      && /phase=(spec|plan)\b/.test(missionState.snapshot.mission.blocked_reason);
    const endpoint = retryingPreparation ? "retry-preparation" : definition.endpoint;
    missionState.operation = await harnessRequest(
      `/v1/actions/${endpoint}`,
      jsonOptions("POST", body),
    );
    renderMission();
    if (definition.endpoint === "grill") activateInspectorTab("chat");
    scheduleMissionRefresh();
  } catch (error) {
    showMissionError(error);
  }
}

async function openMissionDocument(logicalId) {
  try {
    let missionDocument;
    try {
      missionDocument = await harnessRequest(`/v1/documents/${encodeURIComponent(logicalId)}`);
    } catch (error) {
      if (error.status !== 404 || logicalId !== "mission/idea") throw error;
      missionDocument = { logical_id: logicalId, revision: 0, content: "# Mission idea\n\n" };
    }
    missionState.selectedDocument = logicalId;
    missionState.documentRevision = missionDocument.revision;
    document.querySelector("#code-title").textContent = documentLabel(logicalId);
    document.querySelector("#code-meta").textContent = `${logicalId} / revision ${missionDocument.revision}`;
    document.querySelector("#code-status").textContent = "DOC";
    document.querySelector("#code-status").className = "code-status document";
    document.querySelector("#code-status").hidden = false;
    document.querySelector("#document-content").value = missionDocument.content;
    document.querySelector("#document-revision").textContent = `Revision ${missionDocument.revision}`;
    document.querySelector("#document-save-status").textContent = "";
    document.querySelector("#save-document").hidden = false;
    document.querySelector("#close-document").hidden = false;
    dispatchEvent(new CustomEvent("mission-document-opened"));
    codeContent.hidden = true;
    codeEmpty.hidden = true;
    documentEditor.hidden = false;
    await setDocumentMode("preview");
    renderDocuments();
  } catch (error) {
    showMissionError(error);
  }
}

function appendJsonValue(container, label, value) {
  if (value === "" || value === null || value === undefined || (Array.isArray(value) && !value.length)) return;
  const row = document.createElement("div");
  row.className = "json-field";
  const key = document.createElement("dt");
  key.textContent = label;
  const content = document.createElement("dd");
  content.textContent = Array.isArray(value) ? value.join(", ") : String(value);
  row.append(key, content);
  container.append(row);
}

function renderTaskWorkplan(preview, tasks) {
  const heading = document.createElement("div");
  heading.className = "workplan-heading";
  const title = document.createElement("h1");
  title.textContent = "Workplan";
  const count = document.createElement("span");
  count.textContent = `${tasks.length} ${tasks.length === 1 ? "task" : "tasks"}`;
  heading.append(title, count);
  const list = document.createElement("ol");
  list.className = "workplan-list";
  tasks.forEach((task) => {
    const item = document.createElement("li");
    item.className = `workplan-task ${String(task.status || "pending").toLowerCase()}`;
    const header = document.createElement("header");
    const identity = document.createElement("span");
    identity.className = "workplan-identity";
    identity.textContent = task.id || "Task";
    const taskTitle = document.createElement("h2");
    taskTitle.textContent = task.title || "Untitled task";
    const badges = document.createElement("span");
    badges.className = "workplan-badges";
    if (task.complexity) {
      const complexity = document.createElement("b");
      complexity.textContent = task.complexity;
      complexity.title = "Complexity";
      badges.append(complexity);
    }
    const status = document.createElement("i");
    status.textContent = readable(task.status || "pending");
    badges.append(status);
    header.append(identity, taskTitle, badges);
    const details = document.createElement("dl");
    appendJsonValue(details, "Depends on", task.dependencies);
    appendJsonValue(details, "Covers", task.covers);
    appendJsonValue(details, "Targets", task.target_nodes);
    appendJsonValue(details, "Failure", task.failure_reason);
    item.append(header);
    if (details.children.length) item.append(details);
    list.append(item);
  });
  preview.replaceChildren(heading, list);
}

function renderJsonPreview(preview, value) {
  if (Array.isArray(value) && value.every((item) => item && typeof item === "object" && !Array.isArray(item) && ("id" in item || "title" in item))) {
    renderTaskWorkplan(preview, value);
    return;
  }
  const code = document.createElement("code");
  code.textContent = JSON.stringify(value, null, 2);
  const pre = document.createElement("pre");
  pre.className = "json-preview";
  pre.append(code);
  preview.replaceChildren(pre);
}

async function renderDocumentPreview() {
  const preview = document.querySelector("#document-preview");
  const source = document.querySelector("#document-content").value;
  try {
    renderJsonPreview(preview, JSON.parse(source));
    return;
  } catch (error) {
    // Non-JSON documents continue through the Markdown renderer.
  }
  await globalThis.RichContentRenderer.render(preview, source, { prefix: "mission-mermaid" });
}

async function setDocumentMode(mode) {
  missionState.documentMode = mode;
  const editing = mode === "edit";
  document.querySelector("#document-content").hidden = !editing;
  document.querySelector("#document-preview").hidden = editing;
  document.querySelectorAll("[data-document-mode]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.documentMode === mode));
  });
  if (!editing) await renderDocumentPreview();
}

function closeMissionDocument() {
  if (documentEditor.hidden) return;
  documentEditor.hidden = true;
  document.querySelector("#save-document").hidden = true;
  document.querySelector("#close-document").hidden = true;
  missionState.selectedDocument = null;
  renderDocuments();
  if (state.selected && graphNode(state.selected)?.source) renderCodePanel();
  else codeEmpty.hidden = false;
  dispatchEvent(new CustomEvent("mission-document-closed"));
}

async function saveOpenDocument() {
  const logicalId = missionState.selectedDocument;
  if (!logicalId) return;
  const status = document.querySelector("#document-save-status");
  status.textContent = "Saving";
  try {
    const result = await harnessRequest(
      `/v1/documents/${encodeURIComponent(logicalId)}`,
      jsonOptions("PUT", {
        content: document.querySelector("#document-content").value,
        base_revision: missionState.documentRevision,
        command_id: crypto.randomUUID(),
      }),
    );
    missionState.documentRevision = result.revision;
    document.querySelector("#document-revision").textContent = `Revision ${result.revision}`;
    status.textContent = "Saved";
    await refreshMission({ mergeGraph: false });
  } catch (error) {
    status.textContent = error.status === 409 ? "Newer revision available" : error.message;
    if (error.status === 409) await openMissionDocument(logicalId);
  }
}

function locatorForVisualNode(node) {
  if (node.locator) return node.locator;
  if (node.target_path) return node.qualified_name ? `${node.target_path}:${node.qualified_name}` : node.target_path;
  if (node.kind === "module") return node.source || null;
  if (!node.source || node.kind === "package") return null;
  const names = [];
  let current = node;
  while (current && !["module", "package"].includes(current.kind)) {
    names.unshift(current.label);
    current = graphNode(current.parent);
  }
  return names.length ? `${node.source}:${names.join(".")}` : node.source;
}

function visualLevel(node) {
  if (node.kind === "package" && !node.parent) return "SYSTEM";
  if (["package", "module"].includes(node.kind)) return "PACKAGE";
  return "CODE";
}

function statusIntent(status, item = {}) {
  if (status === "accepted") return item.designIntent || "KEEP";
  return { observed: "KEEP", proposed: "CREATE", modified: "CHANGE", removed: "REMOVE" }[status || "observed"];
}

function intentStatus(intent) {
  return { KEEP: "observed", CREATE: "proposed", CHANGE: "modified", REMOVE: "removed" }[intent] || "observed";
}

function visualKind(level, label, targetPath = "") {
  if (level === "SYSTEM") return "package";
  if (level === "PACKAGE") return "module";
  if (isSourceModuleLabel(label, targetPath)) return "module";
  return /^[a-z_]/.test(label || "") ? "function" : "class";
}

function isSourceModuleLabel(label = "", targetPath = "") {
  const value = `${targetPath || ""} ${label || ""}`.trim();
  return /(?:^|[\s(])[^\s()]+\.(?:py|pyi|js|jsx|mjs|cjs|ts|tsx|java|go|rs|rb|php|cs|c|h|cc|cpp|hpp)(?:$|[\s)])/i.test(value);
}

function mergeMissionDesign() {
  if (!missionState.graphReady || !state.baseGraph || !missionState.design) return;
  const designFingerprint = JSON.stringify({
    source: state.baseGraph.source || "",
    root: state.baseGraph.root || "",
    nodes: state.baseGraph.nodes.length,
    edges: state.baseGraph.edges.length,
    designRevision: missionState.design.design_revision || 0,
    observedRevision: missionState.design.observed_revision || 0,
    realization: missionState.design.realization || null,
    dirty: missionState.designDirty,
  });
  if (missionState.mergedDesignFingerprint === designFingerprint && state.graph) return;
  const graph = normalizeGraph(structuredClone(state.baseGraph));
  const visualByLocator = new Map();
  graph.nodes.forEach((node) => {
    const locator = locatorForGraphNode(graph, node);
    if (locator) visualByLocator.set(locator, node);
    if (node.kind === "package") {
      const packageLocator = globalThis.HeroMissionGraphState.packageMissionLocator(graph, node);
      if (packageLocator) {
        visualByLocator.set(packageLocator, node);
        visualByLocator.set(`${packageLocator}/__init__.py`, node);
      }
    }
  });
  const visualByDesignId = new Map();
  missionState.design.nodes.forEach((designNode) => {
    let visual = designNode.locator ? visualByLocator.get(designNode.locator) : null;
    visual ||= graph.nodes.find((node) => node.id === designNode.id);
    if (!visual && globalThis.HeroMissionGraphState.isSemanticMissionRoot(designNode)) {
      // Design contracts often name the repository root semantically, while
      // the extractor identifies it as package:<directory-name>.
      visual = graph.nodes.find((node) => node.id === graph.root);
    }
    if (!visual) {
      visual = {
        id: designNode.id,
        label: designNode.label,
        kind: designNode.kind && designNode.kind !== "unknown"
          ? designNode.kind
          : visualKind(designNode.level, designNode.label, designNode.target_path),
        parent: null,
        line: 0,
        end_line: 0,
        source: "",
      };
      graph.nodes.push(visual);
    }
    visual.designId = designNode.id;
    visual.locator = designNode.locator;
    visual.designDescription = designNode.description;
    visual.target_path = designNode.target_path || "";
    visual.qualified_name = designNode.qualified_name || "";
    visual.signature = designNode.signature || "";
    visual.docstring = designNode.docstring || "";
    visual.satisfies = [...(designNode.satisfies || [])];
    visual.acceptance = [...(designNode.acceptance || [])];
    visual.resolution = designNode.resolution;
    visual.designIntent = designNode.intent;
    visual.realization = missionState.design.realization?.nodes?.[designNode.id] || null;
    visual.status = visual.realization?.status === "accepted" ? "accepted" : intentStatus(designNode.intent);
    visualByDesignId.set(designNode.id, visual);
  });
  missionState.design.nodes.forEach((designNode) => {
    const visual = visualByDesignId.get(designNode.id);
    const parent = visualByDesignId.get(designNode.parent_id);
    if (visual && parent) visual.parent = parent.id;
  });
  missionState.design.nodes.forEach((designNode) => {
    if (!designNode.parent_id) return;
    const visual = visualByDesignId.get(designNode.id);
    const parent = visualByDesignId.get(designNode.parent_id);
    if (!visual || !parent) return;
    const designKey = `contains|${designNode.parent_id}|${designNode.id}`;
    let containment = graph.edges.find((edge) => edge.designKey === designKey)
      || graph.edges.find((edge) => edge.kind === "contains" && edge.source === parent.id && edge.target === visual.id);
    if (!containment) {
      containment = {
        id: `design:${designKey}`,
        source: parent.id,
        target: visual.id,
        kind: "contains",
        label: "contains",
        properties: {},
        generated: true,
      };
      graph.edges.push(containment);
    }
    containment.designKey = designKey;
    containment.designIntent = designNode.intent;
    containment.designProvenance = designNode.provenance || "AGENT";
    containment.status = intentStatus(designNode.intent);
  });
  missionState.design.edges.forEach((designEdge, index) => {
    const source = visualByDesignId.get(designEdge.source);
    const target = visualByDesignId.get(designEdge.target);
    if (!source || !target) return;
    const designKey = `${designEdge.source}|${designEdge.target}|${designEdge.relation}`;
    let edge = graph.edges.find((candidate) => candidate.designKey === designKey)
      || graph.edges.find((candidate) => candidate.source === source.id && candidate.target === target.id && candidate.kind === designEdge.relation);
    if (!edge) {
      edge = globalThis.HeroMissionGraphState.normalizeMissionDesignEdge(
        designEdge,
        source.id,
        target.id,
        missionState.design.realization?.edges?.[designKey] || null,
        index,
      );
      graph.edges.push(edge);
    }
    const normalized = globalThis.HeroMissionGraphState.normalizeMissionDesignEdge(
      designEdge,
      source.id,
      target.id,
      missionState.design.realization?.edges?.[designKey] || null,
      index,
    );
    Object.assign(edge, normalized, { id: edge.id });
  });
  missionState.canonicalGraph = structuredClone(graph);
  if (missionState.designDirty && missionState.localDraft && missionState.localBaseGraph) {
    globalThis.HeroMissionGraphState.applyLocalDraft(graph, missionState.localBaseGraph, missionState.localDraft);
  }
  state.graph = normalizeGraph(graph);
  rebuildGraphIndexes();
  if (!graphNode(state.scope)) state.scope = graph.root || graph.nodes.find((node) => !node.parent)?.id;
  // Reveal exact change paths in the graph without expanding every sibling in
  // those packages. The Explorer may still open the parent folders so the
  // proposed nodes are discoverable there as well.
  state.revealedGraphNodes = new Set(
    state.graph.nodes
      .filter((node) => !["observed", "accepted"].includes(node.status || "observed"))
      .map((node) => node.id),
  );
  state.revealedGraphNodes.forEach((nodeId) => {
    let parent = graphNode(nodeId)?.parent;
    while (parent && parent !== state.scope) {
      state.treeExpanded.add(parent);
      parent = graphNode(parent)?.parent;
    }
  });
  if (state.selected && !graphNode(state.selected)) state.selected = null;
  if (state.selectedRelation && !state.graph.edges.some((edge) => edge.id === state.selectedRelation)) {
    state.selectedRelation = null;
  }
  missionState.mergedDesignFingerprint = designFingerprint;
  invalidateLayout();
  renderFileTree();
  renderBreadcrumbs();
  updateGraphCount();
  updateTools();
  render();
}

function locatorForGraphNode(graph, node) {
  if (node.kind === "module") return node.source || null;
  if (!node.source || node.kind === "package") return null;
  const names = [];
  let current = node;
  while (current && !["module", "package"].includes(current.kind)) {
    names.unshift(current.label);
    current = graph.nodes.find((candidate) => candidate.id === current.parent);
  }
  return names.length ? `${node.source}:${names.join(".")}` : node.source;
}

function desiredDesignState() {
  const backendNodes = new Map((missionState.design?.nodes || []).map((node) => [node.id, node]));
  const activeEdges = state.graph.edges.filter((edge) => (edge.status || "observed") !== "observed" || edge.designKey);
  const requiredVisualIds = new Set(activeEdges.flatMap((edge) => [edge.source, edge.target]));
  const candidates = state.graph.nodes.filter((node) => (node.status || "observed") !== "observed" || node.designId || requiredVisualIds.has(node.id));
  const designIds = new Map();
  candidates.forEach((node) => {
    const locator = locatorForVisualNode(node);
    const matching = [...backendNodes.values()].find((item) => locator && item.locator === locator);
    designIds.set(node.id, node.designId || matching?.id || (node.status === "proposed" ? node.id : `observed:${node.id}`));
  });
  const nodes = candidates.map((node) => {
    const contract = globalThis.HeroProposalContract.contractPayload(node);
    return ({
    id: designIds.get(node.id),
    label: node.label,
    level: visualLevel(node),
    ...contract,
    provenance: node.designProvenance || backendNodes.get(designIds.get(node.id))?.provenance || "HUMAN",
    location: "IN_REPOSITORY",
    intent: statusIntent(node.status, node),
    parent_id: designIds.get(node.parent) || null,
    locator: locatorForVisualNode(node),
  });
  });
  const edges = activeEdges.map((edge) => ({
    source: designIds.get(edge.source),
    target: designIds.get(edge.target),
    relation: edge.label?.trim() || edge.kind,
    provenance: edge.designProvenance || "HUMAN",
    intent: statusIntent(edge.status, edge),
  })).filter((edge) => edge.source && edge.target);
  return { nodes, edges };
}

function designOperations() {
  const desired = desiredDesignState();
  const currentNodes = new Map((missionState.design?.nodes || []).map((node) => [node.id, node]));
  const currentEdges = new Map((missionState.design?.edges || []).map((edge) => [`${edge.source}|${edge.target}|${edge.relation}`, edge]));
  const desiredNodes = new Map(desired.nodes.map((node) => [node.id, node]));
  const desiredEdges = new Map(desired.edges.map((edge) => [`${edge.source}|${edge.target}|${edge.relation}`, edge]));
  const operations = [];

  currentEdges.forEach((edge, key) => {
    const replacement = desiredEdges.get(key);
    if (!replacement || replacement.intent !== edge.intent) operations.push({ op: "remove_edge", source: edge.source, target: edge.target, relation: edge.relation });
  });
  desiredNodes.forEach((node, id) => {
    const current = currentNodes.get(id);
    if (!current) {
      operations.push({ op: "add_node", ...node });
      return;
    }
    const mutable = ["label", "level", "kind", "location", "intent", "parent_id", "locator", "description", "target_path", "qualified_name", "signature", "docstring", "satisfies", "acceptance"];
    const differs = (field) => ["satisfies", "acceptance"].includes(field)
      ? JSON.stringify(current[field] || []) !== JSON.stringify(node[field] || [])
      : (current[field] ?? null) !== (node[field] ?? null);
    const changes = Object.fromEntries(mutable.filter(differs).map((field) => [field, node[field]]));
    if (Object.keys(changes).length) operations.push({ op: "update_node", id, ...changes });
  });
  desiredEdges.forEach((edge, key) => {
    const current = currentEdges.get(key);
    if (!current || current.intent !== edge.intent) operations.push({ op: "add_edge", ...edge });
  });
  currentNodes.forEach((node, id) => {
    if (!desiredNodes.has(id)) operations.push({ op: "remove_node", id });
  });
  return operations;
}

async function synchronizeDesign() {
  if (!missionState.host?.running) return;
  const status = document.querySelector("#design-sync-status");
  status.textContent = "Saving map";
  const operations = designOperations();
  if (!operations.length) {
    missionState.designDirty = false;
    missionState.localDraft = null;
    missionState.localBaseGraph = null;
    updateDesignSyncState();
    return;
  }
  try {
    const result = await harnessRequest(
      "/v1/design/operations",
      jsonOptions("POST", {
        operation_id: crypto.randomUUID(),
        base_revision: missionState.design.design_revision,
        operations,
      }),
    );
    if (result.status !== "APPLIED" && result.status !== "DUPLICATE") throw new Error(result.detail || result.status);
    missionState.designDirty = false;
    missionState.localDraft = null;
    missionState.localBaseGraph = null;
    await refreshMission();
    status.textContent = `Saved at revision ${result.design_revision}`;
    updateDesignSyncState();
  } catch (error) {
    status.textContent = error.status === 409 ? "Map changed elsewhere; reload and retry" : error.message;
    if (error.status === 409) await refreshMission();
    throw error;
  }
}

function updateDesignSyncState() {
  const button = document.querySelector("#sync-design");
  const supported = missionState.capabilities?.features?.design_cas !== false;
  button.disabled = !missionState.host?.running || !missionState.designDirty || !supported;
  document.querySelector("#design-sync-status").textContent = missionState.host?.running
    ? !supported ? "Map editing unavailable" : missionState.designDirty ? "Unsaved map changes" : `HARNESS revision ${missionState.design?.design_revision || 0}`
    : "Local draft";
}

function showMissionError(error) {
  document.querySelector("#mission-form-status").textContent = error.message || "Mission request failed";
  document.querySelector("#mission-summary").textContent = error.message || "Mission request failed";
}

async function openProjectDialog() {
  missionState.host = await jsonRequest("/api/harness/status");
  renderHostStatus();
  const input = document.querySelector("#project-path");
  input.value = missionState.host.project_selected ? missionState.host.project_dir || "" : "";
  document.querySelector("#project-form-status").textContent = "";
  projectDialog.showModal();
  input.focus();
  input.select();
}

async function selectLocalProject(projectPath) {
  const currentHost = await jsonRequest("/api/harness/status");
  missionState.host = currentHost;
  if (currentHost.running) {
    const confirmed = confirm("Opening another project will stop the active HARNESS worker. Continue?");
    if (!confirmed) return false;
    await jsonRequest("/api/harness", { method: "DELETE" });
    missionState.snapshot = null;
    missionState.operation = null;
    missionState.activity = [];
  }
  missionState.host = await jsonRequest("/api/project/select", jsonOptions("POST", { path: projectPath }));
  await loadExperiment({ restoreLocalDesign: false });
  renderHostStatus();
  activateInspectorTab("chat");
  return true;
}

document.querySelectorAll("[data-inspector-tab]").forEach((button) => {
  button.addEventListener("click", () => activateInspectorTab(button.dataset.inspectorTab));
});

document.querySelector("#project-open").addEventListener("click", async () => {
  try {
    await openProjectDialog();
  } catch (error) {
    showMissionError(error);
  }
});
document.querySelector("#project-close").addEventListener("click", () => projectDialog.close());
document.querySelector("#project-cancel").addEventListener("click", () => projectDialog.close());
projectForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const status = document.querySelector("#project-form-status");
  const submit = document.querySelector("#project-submit");
  const projectPath = document.querySelector("#project-path").value.trim();
  status.textContent = "Opening project";
  submit.disabled = true;
  try {
    const selected = await selectLocalProject(projectPath);
    if (!selected) {
      status.textContent = "Project change cancelled";
      return;
    }
    document.querySelector("#mission-form-status").textContent = "";
    projectDialog.close();
  } catch (error) {
    status.textContent = error.message || "Could not open project";
  } finally {
    submit.disabled = false;
  }
});
document.querySelector("#mission-launch").addEventListener("click", () => {
  if (missionState.host?.running) activateInspectorTab("mission");
  else missionDialog.showModal();
});
document.querySelector("#mission-close").addEventListener("click", () => missionDialog.close());
document.querySelector("#mission-file").addEventListener("change", async (event) => {
  const [file] = event.target.files;
  if (file) document.querySelector("#mission-idea").value = await file.text();
});
document.querySelector("#select-project").addEventListener("click", async () => {
  const formStatus = document.querySelector("#mission-form-status");
  formStatus.textContent = "";
  try {
    await openProjectDialog();
  } catch (error) {
    formStatus.textContent = error.message || "Could not select project";
  }
});
missionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formStatus = document.querySelector("#mission-form-status");
  formStatus.textContent = "Starting HARNESS";
  try {
    missionState.host = await harnessRequest("/start", jsonOptions("POST", {
      task: document.querySelector("#mission-task").value.trim(),
      branch: document.querySelector("#mission-branch").value.trim(),
      mode: document.querySelector("#mission-mode").value,
      resume: document.querySelector("#mission-resume").checked,
      no_grill: document.querySelector("#mission-no-grill").checked,
    }));
    await refreshMission();
    const idea = document.querySelector("#mission-idea").value;
    const existing = missionState.snapshot.documents.find((item) => item.logical_id === "mission/idea");
    await harnessRequest(
      `/v1/documents/${encodeURIComponent("mission/idea")}`,
      jsonOptions("PUT", {
        content: idea,
        base_revision: existing?.revision || 0,
        command_id: crypto.randomUUID(),
      }),
    );
    await refreshMission();
    formStatus.textContent = "";
    missionDialog.close();
    activateInspectorTab("mission");
  } catch (error) {
    formStatus.textContent = error.message || "Could not start HARNESS";
  }
});
document.querySelector("#mission-stop").addEventListener("click", async () => {
  await harnessRequest("", { method: "DELETE" });
  missionState.host = { ...(missionState.host || {}), running: false };
  missionState.snapshot = null;
  renderHostStatus();
});
document.querySelector("#save-document").addEventListener("click", saveOpenDocument);
document.querySelector("#close-document").addEventListener("click", closeMissionDocument);
document.querySelectorAll("[data-document-mode]").forEach((button) => {
  button.addEventListener("click", () => setDocumentMode(button.dataset.documentMode));
});
document.querySelector("#sync-design").addEventListener("click", () => synchronizeDesign().catch(showMissionError));
document.querySelector("#chat-form").addEventListener("submit", async (event) => {
  if (document.body.dataset.chatMode !== "mission") return;
  event.preventDefault();
  const input = document.querySelector("#chat-input");
  const text = input.value.trim();
  if (!text) return;
  const status = document.querySelector("#chat-status");
  status.textContent = "Sending";
  try {
    await harnessRequest("/v1/commands", jsonOptions("POST", { text }));
    input.value = "";
    status.textContent = "";
  } catch (error) { status.textContent = error.message; }
});
document.querySelector("#chat-done").addEventListener("click", async () => {
  if (document.body.dataset.chatMode !== "mission") return;
  await harnessRequest("/v1/commands", jsonOptions("POST", { text: "/done" }));
});

addEventListener("graph-experiment-ready", () => {
  missionState.graphReady = true;
  missionState.mergedDesignFingerprint = null;
  mergeMissionDesign();
});
addEventListener("graph-design-changed", () => {
  if (!missionState.host?.running) return;
  if (!missionState.designDirty) {
    missionState.localBaseGraph = structuredClone(missionState.canonicalGraph || state.graph);
  }
  missionState.localDraft = structuredClone(state.graph);
  missionState.designDirty = true;
  updateDesignSyncState();
});
addEventListener("code-selection-opened", () => {
  documentEditor.hidden = true;
  document.querySelector("#save-document").hidden = true;
  document.querySelector("#close-document").hidden = true;
  missionState.selectedDocument = null;
});

renderHostStatus();
updateDesignSyncState();
refreshMission().catch((error) => {
  missionState.host = { configured: false, running: false };
  renderHostStatus();
});
