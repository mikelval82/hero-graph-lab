const SVG_NS = "http://www.w3.org/2000/svg";
const DESIGN_STORAGE_KEY = "hero-graph-lab-design-v1";
const flowNavigation = globalThis.HeroFlowNavigation;
const graphViews = globalThis.HeroGraphViews;
const state = {
  graph: null,
  baseGraph: null,
  source: null,
  view: "flow",
  scope: null,
  selected: null,
  selectedRelation: null,
  task: "Explore project structure and execution flow",
  positions: {},
  treeExpanded: new Set(),
  inlineExpanded: new Set(),
  flowJourney: [],
  flowEntryCandidate: null,
  hiddenGraphNodes: new Set(),
  onlyHighlighted: false,
  callTrace: null,
  graphProjection: null,
  drag: null,
  lastNodeClick: null,
  ignoreNextCanvasClick: false,
  connection: null,
  relationSource: null,
  relationDraft: null,
  graphWidth: 1000,
  graphHeight: 680,
  graphZoom: 1,
  graphPan: null,
  layoutLocked: false,
  layoutSnapshot: null,
  currentLayout: null,
  viewStates: { structure: null, flow: null, focus: null },
  focusReturnView: "flow",
  nodeById: new Map(),
  childrenByParent: new Map(),
};
const graphElement = document.querySelector("#graph");
const edgeLayer = document.querySelector("#edges");
const edgeLabelLayer = document.querySelector("#edge-labels");
const nodeLayer = document.querySelector("#nodes");
const connectionPreview = document.querySelector("#connection-preview");
const graphViewport = document.querySelector("#graph-viewport");
const GRAPH_MIN_ZOOM = .1;
const GRAPH_MAX_ZOOM = 2.5;
const GRAPH_FIT_PADDING = 24;

async function copyTextToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.append(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) throw new Error("Clipboard access is unavailable");
}

function createChatCopyButton(content) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "chat-copy-button";
  button.textContent = "Copy";
  button.title = "Copy agent response";
  button.setAttribute("aria-label", "Copy agent response");
  button.addEventListener("click", async () => {
    try {
      await copyTextToClipboard(content);
      button.textContent = "Copied";
      button.classList.add("copied");
      button.setAttribute("aria-label", "Agent response copied");
      setTimeout(() => {
        if (!button.isConnected) return;
        button.textContent = "Copy";
        button.classList.remove("copied");
        button.setAttribute("aria-label", "Copy agent response");
      }, 1600);
    } catch (error) {
      document.querySelector("#chat-status").textContent = error.message || "Could not copy the response";
    }
  });
  return button;
}

globalThis.createChatCopyButton = createChatCopyButton;

function clamp(value, minimum, maximum) {
  return Math.max(minimum, Math.min(maximum, value));
}

function graphBaseScale() {
  return Math.max(.72, (graphViewport.clientWidth || graphWidth()) / state.graphWidth);
}

function applyGraphScale() {
  const scale = graphBaseScale() * state.graphZoom;
  graphElement.style.width = `${Math.ceil(state.graphWidth * scale)}px`;
  graphElement.style.height = `${Math.ceil(state.graphHeight * scale)}px`;
  graphElement.style.marginTop = `${Math.max(0, Math.floor((graphViewport.clientHeight - state.graphHeight * scale) / 2))}px`;
  document.querySelector("#zoom-level").textContent = `${Math.round(state.graphZoom * 100)}%`;
  document.querySelector("#zoom-out").disabled = state.graphZoom <= GRAPH_MIN_ZOOM;
  document.querySelector("#zoom-in").disabled = state.graphZoom >= GRAPH_MAX_ZOOM;
}

function setGraphZoom(zoom, anchorClientX, anchorClientY) {
  const nextZoom = clamp(Math.round(zoom * 100) / 100, GRAPH_MIN_ZOOM, GRAPH_MAX_ZOOM);
  if (nextZoom === state.graphZoom) return;
  const bounds = graphViewport.getBoundingClientRect();
  const anchorX = anchorClientX === undefined ? graphViewport.clientWidth / 2 : anchorClientX - bounds.left;
  const anchorY = anchorClientY === undefined ? graphViewport.clientHeight / 2 : anchorClientY - bounds.top;
  const contentX = (graphViewport.scrollLeft + anchorX) / state.graphZoom;
  const contentY = (graphViewport.scrollTop + anchorY) / state.graphZoom;
  state.graphZoom = nextZoom;
  applyGraphScale();
  graphViewport.scrollLeft = contentX * nextZoom - anchorX;
  graphViewport.scrollTop = contentY * nextZoom - anchorY;
}

function fitGraphToView() {
  const availableWidth = Math.max(1, graphViewport.offsetWidth - GRAPH_FIT_PADDING);
  const availableHeight = Math.max(1, graphViewport.offsetHeight - GRAPH_FIT_PADDING);
  const fittedScale = Math.min(availableWidth / state.graphWidth, availableHeight / state.graphHeight);
  state.graphZoom = clamp(fittedScale / graphBaseScale(), GRAPH_MIN_ZOOM, GRAPH_MAX_ZOOM);
  applyGraphScale();
  graphViewport.scrollTo({
    left: Math.max(0, (graphViewport.scrollWidth - graphViewport.clientWidth) / 2),
    top: Math.max(0, (graphViewport.scrollHeight - graphViewport.clientHeight) / 2),
  });
}

function startGraphPan(event) {
  if (event.button !== 0 && event.button !== 1) return;
  if (event.target.closest(".graph-node, .edge-label, .edge-hit, .connector, .connector-halo")) return;
  event.preventDefault();
  state.graphPan = {
    pointerId: event.pointerId,
    clientX: event.clientX,
    clientY: event.clientY,
    scrollLeft: graphViewport.scrollLeft,
    scrollTop: graphViewport.scrollTop,
  };
  graphViewport.classList.add("panning");
  graphViewport.setPointerCapture(event.pointerId);
}

function moveGraphPan(event) {
  if (!state.graphPan || event.pointerId !== state.graphPan.pointerId) return;
  graphViewport.scrollLeft = state.graphPan.scrollLeft - (event.clientX - state.graphPan.clientX);
  graphViewport.scrollTop = state.graphPan.scrollTop - (event.clientY - state.graphPan.clientY);
}

function stopGraphPan(event) {
  if (!state.graphPan || event.pointerId !== state.graphPan.pointerId) return;
  state.graphPan = null;
  graphViewport.classList.remove("panning");
  if (graphViewport.hasPointerCapture(event.pointerId)) graphViewport.releasePointerCapture(event.pointerId);
}

function graphNode(nodeId) {
  return state.nodeById.get(nodeId);
}

function scopeChildren(scopeId) {
  return state.childrenByParent.get(scopeId) || [];
}

function rebuildGraphIndexes(graph = state.graph) {
  state.nodeById = new Map();
  state.childrenByParent = new Map();
  (graph?.nodes || []).forEach((node) => {
    if (!state.nodeById.has(node.id)) state.nodeById.set(node.id, node);
    if (!state.childrenByParent.has(node.parent)) state.childrenByParent.set(node.parent, []);
    state.childrenByParent.get(node.parent).push(node);
  });
}

function sortedTreeChildren(nodeId) {
  const kindOrder = { package: 0, module: 1, class: 2, interface: 2, type: 3, function: 4, method: 4 };
  return scopeChildren(nodeId).sort((left, right) => {
    const order = (kindOrder[left.kind] ?? 4) - (kindOrder[right.kind] ?? 4);
    return order || left.label.localeCompare(right.label);
  });
}

function expandTreePath(nodeId) {
  let node = graphNode(nodeId);
  while (node) {
    state.treeExpanded.add(node.id);
    node = graphNode(node.parent);
  }
}

function syncTreeSelection() {
  document.querySelectorAll(".tree-row").forEach((row) => {
    const selected = row.dataset.nodeId === state.selected;
    row.classList.toggle("selected", selected);
    row.classList.toggle("scope", row.dataset.nodeId === state.scope);
    row.querySelector(".tree-item")?.setAttribute("aria-selected", String(selected));
  });
}

function selectTreeNode(nodeId) {
  const node = graphNode(nodeId);
  if (!node) return;
  if (!node.parent) {
    navigateToScope(node.id);
    return;
  }
  if (state.scope !== node.parent) {
    clearCallTrace();
    state.scope = node.parent;
    state.flowJourney = [];
    state.flowEntryCandidate = null;
    invalidateLayout();
    renderBreadcrumbs();
    updateGraphCount();
  }
  setSelection(node.id);
}

function activateTreeNode(nodeId) {
  if (canEnterScope(nodeId)) {
    state.treeExpanded.add(nodeId);
    navigateToScope(nodeId);
    return;
  }
  selectTreeNode(nodeId);
}

function treeIconText(kind) {
  return { class: "C", function: "f", method: "m" }[kind] || "";
}

function appendTreeNode(parent, node, depth) {
  const children = sortedTreeChildren(node.id);
  const expanded = state.treeExpanded.has(node.id);
  const item = document.createElement("li");
  item.setAttribute("role", "none");
  const row = document.createElement("div");
  row.className = `tree-row ${node.status || "observed"}`;
  row.dataset.nodeId = node.id;
  row.style.setProperty("--depth", depth);

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = `tree-toggle${children.length ? "" : " placeholder"}`;
  toggle.tabIndex = children.length ? 0 : -1;
  toggle.setAttribute("aria-label", `${expanded ? "Collapse" : "Expand"} ${node.label}`);
  if (children.length) toggle.setAttribute("aria-expanded", String(expanded));
  toggle.addEventListener("click", () => {
    if (!children.length) return;
    if (expanded) state.treeExpanded.delete(node.id);
    else state.treeExpanded.add(node.id);
    renderFileTree();
  });

  const button = document.createElement("button");
  button.type = "button";
  button.className = "tree-item";
  button.setAttribute("role", "treeitem");
  button.setAttribute("aria-level", depth + 1);
  button.setAttribute("aria-selected", String(state.selected === node.id));
  if (children.length) button.setAttribute("aria-expanded", String(expanded));
  button.addEventListener("click", () => selectTreeNode(node.id));
  button.addEventListener("dblclick", () => activateTreeNode(node.id));
  button.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      activateTreeNode(node.id);
    } else if (event.key === "ArrowRight" && children.length) {
      event.preventDefault();
      if (!expanded) { state.treeExpanded.add(node.id); renderFileTree(); }
      else navigateToScope(node.id);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      if (expanded && node.id !== state.graph.root) { state.treeExpanded.delete(node.id); renderFileTree(); }
      else if (node.parent) selectTreeNode(node.parent);
    }
  });

  const icon = document.createElement("span");
  icon.className = `tree-icon ${node.kind}`;
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = treeIconText(node.kind);
  const label = document.createElement("span");
  label.className = "tree-item-label";
  label.textContent = node.label;
  button.append(icon, label);
  row.append(toggle, button);
  item.append(row);

  if (children.length && expanded) {
    const group = document.createElement("ul");
    group.className = "tree-list";
    group.setAttribute("role", "group");
    children.forEach((child) => appendTreeNode(group, child, depth + 1));
    item.append(group);
  }
  parent.append(item);
}

function renderFileTree() {
  const tree = document.querySelector("#file-tree");
  tree.replaceChildren();
  const root = graphNode(state.graph.root || state.graph.nodes.find((node) => !node.parent)?.id);
  if (!root) return;
  const list = document.createElement("ul");
  list.className = "tree-list";
  list.setAttribute("role", "group");
  appendTreeNode(list, root, 0);
  tree.append(list);
  syncTreeSelection();
}

function canEnterScope(nodeId) {
  return graphViews.canEnterScope(graphViewContext(), nodeId);
}

function isDescendantOf(nodeId, ancestorId) {
  return graphViews.isDescendant(graphViewContext(), nodeId, ancestorId);
}

function descendantIds(nodeId) {
  return graphViews.descendantIds(graphViewContext(), nodeId);
}

function outgoingCallTrace(rootId, maxDepth = 1) {
  return graphViews.outgoingCallTrace(state.graph, rootId, maxDepth);
}

function callTraceGraph() {
  return graphViews.callTraceGraph(graphViewContext());
}

function visibleHierarchyNodes(scopeId, expandedNodes = state.inlineExpanded) {
  return graphViews.visibleHierarchyNodes(graphViewContext({ scope: scopeId }), expandedNodes);
}

function flowGraph(expandedNodes = state.inlineExpanded) {
  return graphViews.flowGraph(graphViewContext(), expandedNodes);
}

function structureGraph() {
  return graphViews.structureGraph(graphViewContext());
}

function focusGraph() {
  return graphViews.focusGraph(graphViewContext());
}

function flowActiveNodeId() {
  return graphViews.flowActiveNodeId(state.flowJourney);
}

function flowRelationSnapshot(edge) {
  return graphViews.flowRelationSnapshot(edge);
}

function flowJourneyGraph() {
  return graphViews.flowJourneyGraph(graphViewContext());
}

function graphViewContext(overrides = {}) {
  return {
    graph: state.graph,
    scope: state.scope || state.graph?.root,
    selected: state.selected,
    inlineExpanded: state.inlineExpanded,
    hiddenGraphNodes: state.hiddenGraphNodes,
    callTrace: state.callTrace,
    flowJourney: state.flowJourney,
    nodeById: state.nodeById,
    childrenByParent: state.childrenByParent,
    ...overrides,
  };
}

function navigationGraph() {
  let graph;
  if (state.callTrace) graph = callTraceGraph();
  else if (state.graphProjection) graph = state.graphProjection.graph;
  else if (state.layoutLocked && state.layoutSnapshot) graph = state.layoutSnapshot.graph;
  else if (state.view === "structure") graph = structureGraph();
  else if (state.view === "focus") graph = focusGraph();
  else graph = flowJourneyGraph();
  return state.onlyHighlighted && contextFilterAvailable()
    ? graphViews.highlightedGraph(graph, state.selected)
    : graph;
}

function contextFilterAvailable() {
  return Boolean(state.graph && state.selected && state.view === "flow"
    && !state.callTrace && !state.graphProjection && !state.layoutLocked);
}

function updateContextVisibilityControl() {
  const button = document.querySelector("#context-visibility");
  button.disabled = !contextFilterAvailable();
  button.setAttribute("aria-pressed", String(state.onlyHighlighted));
  button.querySelector("span").textContent = state.onlyHighlighted ? "Show context" : "Only highlighted";
  button.title = state.onlyHighlighted ? "Show dimmed graph context (C)" : "Show only highlighted nodes (C)";
}

function toggleContextVisibility() {
  if (!contextFilterAvailable()) return;
  state.onlyHighlighted = !state.onlyHighlighted;
  invalidateLayout();
  updateGraphCount();
  updateTools();
  render();
  fitGraphToView();
  document.querySelector("#graph-command-status").textContent = state.onlyHighlighted
    ? "Only the selected node and its highlighted neighbors are visible. Press C to restore context."
    : "Dimmed graph context restored.";
}

function graphProjectionKey(graph) {
  return `${graph.nodes.map((node) => node.id).join("|")}::${graph.edges.map((edge) => edge.id).join("|")}`;
}

function captureGraphViewState() {
  if (!state.currentLayout) return;
  state.viewStates[state.view] = {
    layout: structuredClone(state.currentLayout),
    selected: state.selected,
    selectedRelation: state.selectedRelation,
    zoom: state.graphZoom,
    scrollLeft: graphViewport.scrollLeft,
    scrollTop: graphViewport.scrollTop,
  };
}

function invalidateLayout() {
  releaseGraphLayout();
  state.positions = {};
  state.currentLayout = null;
  state.viewStates = { structure: null, flow: null, focus: null };
}

function updateLayoutLockControl() {
  const button = document.querySelector("#lock-layout");
  button.setAttribute("aria-pressed", String(state.layoutLocked));
  button.querySelector("span").textContent = state.layoutLocked ? "Unlock view" : "Lock view";
  button.title = state.layoutLocked ? "Resume dynamic layout" : "Keep visible nodes fixed while inspecting";
}

function releaseGraphLayout() {
  state.layoutLocked = false;
  state.layoutSnapshot = null;
  updateLayoutLockControl();
}

function toggleGraphLayoutLock() {
  if (state.layoutLocked) {
    releaseGraphLayout();
  } else {
    const graph = navigationGraph();
    const positions = currentPositions(graph);
    state.layoutSnapshot = {
      graph: structuredClone(graph),
      positions: structuredClone(positions),
      width: state.graphWidth,
      height: state.graphHeight,
    };
    state.layoutLocked = true;
    updateLayoutLockControl();
  }
  updateGraphCount();
  updateTools();
  render();
}

function selectRelation(edge) {
  if (state.graphProjection) {
    document.querySelector("#graph-command-status").textContent = "Restore the normal graph before editing relationships.";
    return;
  }
  state.selectedRelation = edge.id;
  state.selected = null;
  updateTools();
  syncTreeSelection();
  render();
  dispatchEvent(new CustomEvent("graph-selection-changed"));
  openRelationDialog("edit", edge);
}

function graphPoint(event) {
  const bounds = graphElement.getBoundingClientRect();
  return {
    x: (event.clientX - bounds.left) * (state.graphWidth / bounds.width),
    y: (event.clientY - bounds.top) * (state.graphHeight / bounds.height),
  };
}

function startConnection(event, sourceId, start) {
  event.preventDefault();
  event.stopPropagation();
  state.connection = { sourceId, start, pointerId: event.pointerId };
  connectionPreview.hidden = false;
  connectionPreview.setAttribute("d", curve(start, start));
  graphElement.setPointerCapture(event.pointerId);
}

function moveConnection(event) {
  if (!state.connection || event.pointerId !== state.connection.pointerId) return;
  connectionPreview.setAttribute("d", curve(state.connection.start, graphPoint(event)));
}

function stopConnection(event) {
  if (!state.connection || event.pointerId !== state.connection.pointerId) return;
  const completed = state.connection;
  state.connection = null;
  connectionPreview.hidden = true;
  graphElement.releasePointerCapture(event.pointerId);
  const targetGroup = document.elementFromPoint(event.clientX, event.clientY)?.closest(".graph-node");
  const targetId = targetGroup?.dataset.nodeId;
  if (targetId && targetId !== completed.sourceId) openRelationDialog("add", null, completed.sourceId, targetId);
}

function startDrag(event, nodeId, position) {
  event.stopPropagation();
  state.drag = {
    nodeId,
    pointerId: event.pointerId,
    startClientX: event.clientX,
    startClientY: event.clientY,
    startX: position.x,
    startY: position.y,
    moved: false,
  };
  graphElement.setPointerCapture(event.pointerId);
}

function dragNode(event) {
  if (!state.drag || event.pointerId !== state.drag.pointerId) return;
  if (state.layoutLocked) return;
  const bounds = graphElement.getBoundingClientRect();
  const deltaX = (event.clientX - state.drag.startClientX) * (state.graphWidth / bounds.width);
  const deltaY = (event.clientY - state.drag.startClientY) * (state.graphHeight / bounds.height);
  state.drag.moved ||= Math.abs(deltaX) + Math.abs(deltaY) > 4;
  state.positions[state.drag.nodeId] = {
    x: Math.max(40, Math.min(state.graphWidth - 40, state.drag.startX + deltaX)),
    y: Math.max(40, Math.min(state.graphHeight - 40, state.drag.startY + deltaY)),
  };
  render();
}

function focusRenderedGraphNode(nodeId = state.selected) {
  const node = Array.from(nodeLayer.querySelectorAll(".graph-node"))
    .find((candidate) => candidate.dataset.nodeId === nodeId);
  (node || graphViewport).focus();
}

function stopDrag(event) {
  if (!state.drag || event.pointerId !== state.drag.pointerId) return;
  const completedDrag = state.drag;
  state.drag = null;
  graphElement.releasePointerCapture(event.pointerId);
  state.ignoreNextCanvasClick = true;
  if (completedDrag.moved) {
    saveDesign();
    return;
  }
  const clickTransition = flowNavigation.nodeClickTransition({
    selected: state.selected,
    lastNodeClick: state.lastNodeClick,
    nodeId: completedDrag.nodeId,
    now: performance.now(),
  });
  state.lastNodeClick = clickTransition.lastNodeClick;
  setSelection(clickTransition.selected);
  if (clickTransition.isDoubleClick) {
    if (state.graphProjection) globalThis.HeroDiagrams?.expandProjection(completedDrag.nodeId);
    else if (state.view === "flow" || canEnterScope(completedDrag.nodeId)) expandSelectedNode();
    fitGraphToView();
    focusRenderedGraphNode(completedDrag.nodeId);
  }
}

function setSelection(nodeId) {
  const previousNodeId = state.selected;
  if (state.view === "flow" && previousNodeId && nodeId && previousNodeId !== nodeId) {
    const visibleGraph = navigationGraph();
    const connectedEdge = visibleGraph.edges.find((edge) => (
      edge.source === previousNodeId && edge.target === nodeId
    ) || (
      edge.source === nodeId && edge.target === previousNodeId
    ));
    state.flowEntryCandidate = connectedEdge ? {
      source: previousNodeId,
      target: nodeId,
      relation: flowRelationSnapshot(connectedEdge),
    } : null;
  } else if (state.view === "flow" && (!nodeId || state.flowEntryCandidate?.target !== nodeId)) {
    state.flowEntryCandidate = null;
  }
  if (state.relationSource && nodeId && nodeId !== state.relationSource) {
    const sourceId = state.relationSource;
    state.relationSource = null;
    document.body.classList.remove("relation-command-active");
    document.querySelector("#graph-command-status").textContent = "";
    openRelationDialog("add", null, sourceId, nodeId);
  }
  state.selected = nodeId;
  state.selectedRelation = null;
  const node = state.graph.nodes.find((candidate) => candidate.id === state.selected);
  if (node) renderCodePanel(node);
  updateGraphCount();
  updateTools();
  syncTreeSelection();
  if (state.view === "focus" && !state.graphProjection) {
    render();
    focusRenderedGraphNode(nodeId);
  } else updateGraphSelectionStyles();
  dispatchEvent(new CustomEvent("graph-selection-changed"));
}

function clearSelection() {
  if (!state.selected && !state.selectedRelation) return;
  if (state.view === "focus" && !state.graphProjection) {
    setGraphView(state.focusReturnView || "flow");
    focusRenderedGraphNode();
    return;
  }
  state.selected = null;
  state.selectedRelation = null;
  state.flowEntryCandidate = null;
  updateGraphCount();
  updateTools();
  syncTreeSelection();
  if (state.view === "focus" && !state.graphProjection) render();
  else updateGraphSelectionStyles();
  dispatchEvent(new CustomEvent("graph-selection-changed"));
}

function refreshSelection() {
  setSelection(state.selected);
}

function updateGraphCount() {
  const visibleGraph = navigationGraph();
  const changedNodes = state.graph.nodes.filter((node) => (node.status || "observed") !== "observed").length;
  const changedRelations = state.graph.edges.filter((edge) => (edge.status || "observed") !== "observed" && !edge.generated).length;
  const proposals = changedNodes + changedRelations;
  document.querySelector("#graph-count").textContent = `${visibleGraph.nodes.length} visible / ${state.graph.nodes.length} indexed / ${proposals} changes`;
}

function setGraphView(view) {
  if (!["structure", "flow", "focus"].includes(view) || state.view === view) return;
  if (state.callTrace) {
    clearCallTrace();
    render();
  }
  const sourceView = state.view;
  const selectedAtEntry = state.selected;
  captureGraphViewState();
  releaseGraphLayout();
  if (view === "focus") state.focusReturnView = sourceView;
  state.view = view;
  state.selectedRelation = null;
  let savedView = state.viewStates[view];
  if (view === "focus" && savedView?.selected !== selectedAtEntry) {
    state.viewStates.focus = null;
    savedView = null;
  }
  if (savedView) {
    state.selected = savedView.selected;
    state.selectedRelation = savedView.selectedRelation;
    state.graphZoom = savedView.zoom;
  } else if (view === "focus") {
    state.selected = selectedAtEntry;
  }
  document.querySelectorAll("[data-graph-view]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.graphView === view));
  });
  const viewLabel = view === "structure" ? "Hierarchy" : `${view[0].toUpperCase()}${view.slice(1)}`;
  document.querySelector("#graph-view-label").textContent = `${viewLabel} Graph`;
  updateGraphCount();
  updateTools();
  render();
  if (savedView) {
    graphViewport.scrollTo({ left: savedView.scrollLeft, top: savedView.scrollTop });
  } else {
    fitGraphToView();
  }
  refreshSelection();
}

function updateTools() {
  const node = state.graph?.nodes.find((candidate) => candidate.id === state.selected);
  const visibleNodeIds = state.graph ? new Set(navigationGraph().nodes.map((candidate) => candidate.id)) : new Set();
  const inlineNode = node && visibleNodeIds.has(node.id) && isDescendantOf(node.id, state.scope);
  const projectionActive = Boolean(state.graphProjection);
  const traceButton = document.querySelector("#trace-calls");
  const hasOutgoingCalls = node && ["function", "method"].includes(node.kind) && state.graph.edges.some((edge) => edge.kind === "calls" && edge.status !== "removed" && edge.source === node.id);
  traceButton.disabled = Boolean(state.graphProjection) || state.view !== "flow" || (!state.callTrace && !hasOutgoingCalls);
  traceButton.setAttribute("aria-pressed", String(Boolean(state.callTrace)));
  traceButton.querySelector("span").textContent = state.callTrace ? "Restore view" : "Trace calls";
  document.querySelector("#edit-node").disabled = projectionActive || !node || node.status === "removed";
  document.querySelector("#delete-node").disabled = projectionActive || !node;
  document.querySelector("#delete-node span").textContent = node?.status === "removed" ? "Restore" : "Delete";
  const temporaryFocus = state.view === "focus" && !projectionActive;
  const canFollow = state.view === "flow" && inlineNode && (
    state.flowEntryCandidate?.target === node.id || !state.flowJourney.length
  );
  const canExpand = inlineNode && scopeChildren(node?.id).length && !state.inlineExpanded.has(node.id);
  document.querySelector("#expand-node").disabled = projectionActive ? !node : temporaryFocus || !canExpand && !canFollow;
  document.querySelector("#collapse-node").disabled = projectionActive ? !state.graphProjection.history.length : temporaryFocus || !inlineNode || !state.inlineExpanded.has(node.id);
  document.querySelector("#expand-node span").textContent = projectionActive ? "Expand node" : canFollow && !canExpand ? "Follow" : "Expand";
  document.querySelector("#collapse-node span").textContent = projectionActive ? "Back" : "Collapse";
  document.querySelector("#hide-node").disabled = projectionActive || temporaryFocus || !node || !visibleNodeIds.has(node.id);
  document.querySelector("#reset-view").disabled = projectionActive || !state.inlineExpanded.size && !state.hiddenGraphNodes.size && !Object.keys(state.positions).length;
  document.querySelector("#reset-design").disabled = projectionActive;
  updateContextVisibilityControl();
  globalThis.HeroCommands?.refresh();
}

function setGraphDesignMode(active) {
  document.body.classList.toggle("graph-design-mode", Boolean(active));
  const button = document.querySelector("#design-mode-toggle");
  button.setAttribute("aria-pressed", String(Boolean(active)));
  button.querySelector("span").textContent = active ? "Close design" : "Design";
  button.title = active ? "Hide graph design tools" : "Show graph design tools";
  requestAnimationFrame(() => {
    updateGraphViewport();
    render();
  });
}

function clearCallTrace({ restoreViewport = false } = {}) {
  if (!state.callTrace) return;
  const returnView = state.callTrace.returnView;
  state.callTrace = null;
  if (!returnView) {
    invalidateLayout();
    return;
  }
  state.positions = returnView.positions;
  state.currentLayout = returnView.currentLayout;
  state.viewStates = returnView.viewStates;
  state.graphZoom = returnView.graphZoom;
  state.selected = returnView.selected;
  state.selectedRelation = returnView.selectedRelation;
  state.layoutLocked = returnView.layoutLocked;
  state.layoutSnapshot = returnView.layoutSnapshot;
  updateLayoutLockControl();
  syncTreeSelection();
  if (restoreViewport) {
    requestAnimationFrame(() => {
      applyGraphScale();
      graphViewport.scrollTo({ left: returnView.scrollLeft, top: returnView.scrollTop });
    });
  }
}

function toggleCallTrace() {
  if (state.callTrace) {
    clearCallTrace({ restoreViewport: true });
  } else {
    const trace = outgoingCallTrace(state.selected);
    if (!trace.edgeIds.size) return;
    trace.returnView = {
      positions: structuredClone(state.positions),
      currentLayout: structuredClone(state.currentLayout),
      viewStates: structuredClone(state.viewStates),
      graphZoom: state.graphZoom,
      scrollLeft: graphViewport.scrollLeft,
      scrollTop: graphViewport.scrollTop,
      selected: state.selected,
      selectedRelation: state.selectedRelation,
      layoutLocked: state.layoutLocked,
      layoutSnapshot: structuredClone(state.layoutSnapshot),
    };
    state.callTrace = trace;
    state.positions = {};
    state.currentLayout = null;
    releaseGraphLayout();
  }
  updateGraphCount();
  updateTools();
  render();
  if (state.callTrace) {
    fitGraphToView();
    document.querySelector("#graph-command-status").textContent = `${state.callTrace.nodeDepths.size} nodes in call trace. Press T again to restore the previous view.`;
  } else {
    document.querySelector("#graph-command-status").textContent = "Call trace cleared. Previous view restored.";
    dispatchEvent(new CustomEvent("graph-selection-changed"));
  }
}

function expandSelectedNode() {
  if (state.graphProjection) {
    globalThis.HeroDiagrams?.expandProjection(state.selected);
    return;
  }
  if (state.view === "focus") return;
  const node = graphNode(state.selected);
  if (!node || !isDescendantOf(node.id, state.scope)) return;
  const hasChildren = scopeChildren(node.id).length > 0;
  const expandsNode = hasChildren && !state.inlineExpanded.has(node.id);
  if (state.view === "flow") {
    const candidate = state.flowEntryCandidate?.target === node.id ? state.flowEntryCandidate : null;
    if (!candidate && state.flowJourney.length && flowActiveNodeId() !== node.id && !expandsNode) return;
    if (candidate && !state.flowJourney.some((step) => step.nodeId === candidate.source)) {
      state.flowJourney = flowNavigation.appendStep(state.flowJourney, candidate.source);
    }
    state.flowJourney = flowNavigation.appendStep(state.flowJourney, node.id, {
      fromNodeId: candidate?.source || flowActiveNodeId(),
      relation: candidate?.relation || null,
      expanded: expandsNode,
    });
  }
  if (expandsNode) state.inlineExpanded.add(node.id);
  state.flowEntryCandidate = null;
  invalidateLayout();
  saveDesign();
  renderBreadcrumbs();
  updateGraphCount();
  updateTools();
  render();
}

function collapseSelectedNode() {
  if (state.graphProjection) {
    globalThis.HeroDiagrams?.backProjection();
    return;
  }
  if (state.view === "focus") return;
  const node = graphNode(state.selected);
  if (!node) return;
  const collapsedDescendants = descendantIds(node.id);
  state.inlineExpanded.delete(node.id);
  collapsedDescendants.forEach((nodeId) => state.inlineExpanded.delete(nodeId));
  state.flowJourney = flowNavigation.collapseJourney(state.flowJourney, node.id, collapsedDescendants);
  state.flowEntryCandidate = null;
  invalidateLayout();
  saveDesign();
  renderBreadcrumbs();
  updateGraphCount();
  updateTools();
  render();
}

function hideSelectedNode() {
  const node = graphNode(state.selected);
  if (!node) return;
  if (state.callTrace?.nodeDepths.has(node.id)) clearCallTrace();
  state.hiddenGraphNodes.add(node.id);
  const hiddenNodeIds = descendantIds(node.id);
  descendantIds(node.id).forEach((nodeId) => {
    state.hiddenGraphNodes.add(nodeId);
    state.inlineExpanded.delete(nodeId);
  });
  state.inlineExpanded.delete(node.id);
  hiddenNodeIds.add(node.id);
  state.flowJourney = flowNavigation.pruneJourney(state.flowJourney, hiddenNodeIds);
  state.flowEntryCandidate = null;
  invalidateLayout();
  state.selected = null;
  saveDesign();
  syncTreeSelection();
  renderBreadcrumbs();
  updateTools();
  render();
}

function resetGraphView() {
  const resetFromFocus = state.view === "focus";
  clearCallTrace();
  state.inlineExpanded.clear();
  state.flowJourney = [];
  state.flowEntryCandidate = null;
  state.hiddenGraphNodes.clear();
  state.onlyHighlighted = false;
  invalidateLayout();
  state.selected = null;
  state.selectedRelation = null;
  if (resetFromFocus) {
    state.view = "flow";
    state.focusReturnView = "flow";
    document.querySelectorAll("[data-graph-view]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.graphView === "flow"));
    });
    document.querySelector("#graph-view-label").textContent = "Flow Graph";
  }
  saveDesign();
  syncTreeSelection();
  updateTools();
  render();
}

function scopePath() {
  const path = [];
  let node = graphNode(state.scope);
  while (node) {
    path.unshift(node);
    node = graphNode(node.parent);
  }
  return path;
}

function renderBreadcrumbs() {
  const breadcrumbs = document.querySelector("#scope-breadcrumbs");
  breadcrumbs.replaceChildren();
  scopePath().forEach((node) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "scope-crumb";
    button.textContent = node.label;
    button.addEventListener("click", () => navigateToScope(node.id));
    breadcrumbs.append(button);
  });
  state.flowJourney.forEach((step, index) => {
    const node = graphNode(step.nodeId);
    if (!node) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = `scope-crumb trail-crumb${index === 0 ? " origin-crumb" : ""}`;
    const arrow = step.direction === "reverse" ? "<-" : "->";
    button.textContent = index ? `${arrow} ${node.label}` : node.label;
    button.title = step.relation
      ? `${graphNode(step.fromNodeId)?.label || step.fromNodeId} ${step.relation.kind} ${arrow} ${node.label}`
      : index ? `Continue at ${node.label}` : "Flow journey origin";
    button.addEventListener("click", () => {
      state.flowJourney.slice(index + 1).filter((candidate) => candidate.expanded).forEach((candidate) => {
        state.inlineExpanded.delete(candidate.nodeId);
        descendantIds(candidate.nodeId).forEach((descendantId) => state.inlineExpanded.delete(descendantId));
      });
      state.flowJourney = flowNavigation.truncateJourney(state.flowJourney, index);
      setSelection(node.id);
      state.flowEntryCandidate = null;
      invalidateLayout();
      saveDesign();
      renderBreadcrumbs();
      updateGraphCount();
      updateTools();
      render();
    });
    breadcrumbs.append(button);
  });
  breadcrumbs.scrollLeft = breadcrumbs.scrollWidth;
  const parent = graphNode(state.scope)?.parent;
  document.querySelector("#scope-up").disabled = !state.flowJourney.length && !parent;
}

function navigateGraphBack() {
  if (!state.flowJourney.length) {
    navigateToScope(graphNode(state.scope)?.parent);
    return;
  }
  const removedStep = state.flowJourney.pop();
  if (removedStep.expanded) {
    state.inlineExpanded.delete(removedStep.nodeId);
    descendantIds(removedStep.nodeId).forEach((nodeId) => state.inlineExpanded.delete(nodeId));
  }
  invalidateLayout();
  saveDesign();
  renderBreadcrumbs();
  setSelection(flowActiveNodeId());
  state.flowEntryCandidate = null;
  render();
}

function navigateToScope(scopeId) {
  if (!scopeId || !graphNode(scopeId)) return;
  clearCallTrace();
  state.scope = scopeId;
  state.selected = null;
  state.selectedRelation = null;
  state.lastNodeClick = null;
  state.flowJourney = [];
  state.flowEntryCandidate = null;
  invalidateLayout();
  expandTreePath(scopeId);
  renderFileTree();
  renderBreadcrumbs();
  updateGraphCount();
  updateTools();
  render();
}

function saveDesign() {
  try {
    localStorage.setItem(DESIGN_STORAGE_KEY, JSON.stringify({
      source: state.graph.source,
      graph: state.graph,
      positions: state.positions,
      inlineExpanded: [...state.inlineExpanded],
      flowJourney: state.flowJourney,
      hiddenGraphNodes: [...state.hiddenGraphNodes],
    }));
  } catch (error) {
    console.warn("Could not save local graph design.", error);
  }
  renderFileTree();
  updateGraphCount();
}

function reconcileStoredDesign(baseGraph, storedGraph) {
  const reconciled = structuredClone(baseGraph);
  const nodesById = new Map(reconciled.nodes.map((node) => [node.id, node]));
  const proposedNodes = [];
  for (const storedNode of storedGraph.nodes || []) {
    const current = nodesById.get(storedNode.id);
    if (!current) {
      if (storedNode.status === "proposed") proposedNodes.push(structuredClone(storedNode));
      continue;
    }
    const evidence = { source: current.source, line: current.line, end_line: current.end_line };
    Object.assign(current, structuredClone(storedNode), evidence);
  }
  let added = true;
  while (added && proposedNodes.length) {
    added = false;
    for (let index = proposedNodes.length - 1; index >= 0; index -= 1) {
      const node = proposedNodes[index];
      if (node.parent && !nodesById.has(node.parent)) continue;
      reconciled.nodes.push(node);
      nodesById.set(node.id, node);
      proposedNodes.splice(index, 1);
      added = true;
    }
  }

  const storedNodesById = new Map((storedGraph.nodes || []).map((node) => [node.id, node]));
  reconciled.edges = reconciled.edges.filter((edge) => {
    if (edge.kind !== "contains") return true;
    const storedTarget = storedNodesById.get(edge.target);
    return !storedTarget || storedTarget.status !== "modified" || storedTarget.parent === edge.source;
  });
  const edgesById = new Map(reconciled.edges.map((edge) => [edge.id, edge]));
  for (const storedEdge of storedGraph.edges || []) {
    const current = edgesById.get(storedEdge.id);
    if (current) {
      const endpoints = { source: current.source, target: current.target };
      Object.assign(current, structuredClone(storedEdge), endpoints);
      continue;
    }
    if (!["proposed", "modified"].includes(storedEdge.status)) continue;
    if (!nodesById.has(storedEdge.source) || !nodesById.has(storedEdge.target)) continue;
    const edge = structuredClone(storedEdge);
    reconciled.edges.push(edge);
    edgesById.set(edge.id, edge);
  }
  return reconciled;
}

function markGraphDesignChanged() {
  dispatchEvent(new CustomEvent("graph-design-changed"));
}

function restoreDesign(baseGraph) {
  try {
    const stored = JSON.parse(localStorage.getItem(DESIGN_STORAGE_KEY));
    if (stored?.source === baseGraph.source && Array.isArray(stored.graph?.nodes) && Array.isArray(stored.graph?.edges)) {
      state.positions = stored.positions?.flow || stored.positions || state.positions;
      state.inlineExpanded = new Set(stored.inlineExpanded || []);
      state.flowJourney = Array.isArray(stored.flowJourney)
        ? flowNavigation.normalizeJourney(stored.flowJourney)
        : flowNavigation.migrateLegacyJourney(stored.flowOrigin, stored.flowTrail);
      state.hiddenGraphNodes = new Set(stored.hiddenGraphNodes || []);
      return reconcileStoredDesign(baseGraph, stored.graph);
    }
  } catch (error) {
    localStorage.removeItem(DESIGN_STORAGE_KEY);
  }
  return baseGraph;
}

function normalizeGraph(graph) {
  const nodeById = new Map(graph.nodes.map((node) => [node.id, node]));
  graph.nodes.forEach((node) => {
    node.status ||= "observed";
    // Older agent/local drafts sometimes classified a filename such as
    // `markdown_adapter.py` as a function because it starts with lowercase.
    // A source-file label is unambiguously a module, unless it already has a
    // callable contract that identifies a real function.
    if (node.kind === "function" && isSourceModuleLabel(node.label, node.target_path)
      && !node.qualified_name && !node.signature) {
      node.kind = "module";
    }
  });
  graph.edges.forEach((edge, index) => {
    edge.id ||= `observed:${index}:${edge.source}:${edge.kind}:${edge.target}`;
    edge.status ||= "observed";
    edge.properties ||= {};
    const target = nodeById.get(edge.target);
    if (edge.status === "proposed" && edge.kind === "contains" && target?.status === "proposed" && !edge.label) edge.generated = true;
  });
  rebuildGraphIndexes(graph);
  return graph;
}

function isSourceModuleLabel(label = "", targetPath = "") {
  const value = `${targetPath || ""} ${label || ""}`.trim();
  return /(?:^|[\s(])[^\s()]+\.(?:py|pyi|js|jsx|mjs|cjs|ts|tsx|java|go|rs|rb|php|cs|c|h|cc|cpp|hpp)(?:$|[\s)])/i.test(value);
}

async function loadExperiment({ restoreLocalDesign = true } = {}) {
  try {
    const [graphResponse, sourceResponse] = await Promise.all([fetch("/api/graph"), fetch("/api/source")]);
    if (!graphResponse.ok || !sourceResponse.ok) throw new Error("Request failed");
    const extractedGraph = await graphResponse.json();
    state.source = await sourceResponse.json();
    state.flowJourney = [];
    state.flowEntryCandidate = null;
    state.onlyHighlighted = false;
    state.viewStates = { structure: null, flow: null, focus: null };
    state.focusReturnView = "flow";
    state.currentLayout = null;
    normalizeGraph(extractedGraph);
    state.baseGraph = structuredClone(extractedGraph);
    state.graph = normalizeGraph(restoreLocalDesign ? restoreDesign(extractedGraph) : extractedGraph);
    state.scope = state.graph.root || state.graph.nodes.find((node) => !node.parent)?.id;
    state.treeExpanded = new Set(state.graph.root ? [state.graph.root] : []);
    document.querySelector("#source-name").textContent = state.graph.source;
    updateGraphViewport(); renderFileTree(); renderBreadcrumbs(); updateGraphCount(); updateTools(); render();
    dispatchEvent(new CustomEvent("graph-experiment-ready"));
  } catch (error) {
    graphElement.hidden = true; document.querySelector("#empty-state").hidden = false;
  }
}

graphElement.addEventListener("pointermove", dragNode);
graphElement.addEventListener("pointermove", moveConnection);
graphElement.addEventListener("pointerup", stopDrag);
graphElement.addEventListener("pointerup", stopConnection);
graphElement.addEventListener("pointercancel", stopDrag);
graphElement.addEventListener("pointercancel", stopConnection);
graphElement.addEventListener("click", (event) => {
  if (state.ignoreNextCanvasClick) {
    state.ignoreNextCanvasClick = false;
    return;
  }
  if (!event.target.closest(".graph-node")) clearSelection();
});
graphViewport.addEventListener("wheel", (event) => {
  if (!event.ctrlKey) return;
  event.preventDefault();
  setGraphZoom(state.graphZoom * (event.deltaY < 0 ? 1.12 : .89), event.clientX, event.clientY);
}, { passive: false });
graphViewport.addEventListener("pointerdown", startGraphPan);
graphViewport.addEventListener("pointermove", moveGraphPan);
graphViewport.addEventListener("pointerup", stopGraphPan);
graphViewport.addEventListener("pointercancel", stopGraphPan);
document.querySelector("#zoom-out").addEventListener("click", () => setGraphZoom(state.graphZoom - .1));
document.querySelector("#zoom-in").addEventListener("click", () => setGraphZoom(state.graphZoom + .1));
document.querySelector("#zoom-fit").addEventListener("click", fitGraphToView);
document.querySelector("#scope-up").addEventListener("click", navigateGraphBack);
document.querySelector("#collapse-tree").addEventListener("click", () => {
  state.treeExpanded = new Set([state.graph.root]);
  renderFileTree();
});
document.querySelector("#lock-layout").addEventListener("click", toggleGraphLayoutLock);
document.querySelector("#reset-view").addEventListener("click", resetGraphView);
document.querySelector("#design-mode-toggle").addEventListener("click", (event) => {
  setGraphDesignMode(event.currentTarget.getAttribute("aria-pressed") !== "true");
});
document.querySelector("#graph-more").addEventListener("click", (event) => {
  if (event.target.closest("button")) event.currentTarget.removeAttribute("open");
});

const pythonTokenPattern = /(#[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b(?:from|import|class|def|return|if|else|elif|for|while|in|is|not|and|or|as|with|async|await|raise|try|except|finally|yield|lambda|pass|break|continue)\b|\b(?:True|False|None)\b|\b\d+(?:\.\d+)?\b)/g;

function tokenClass(value) {
  if (value.startsWith("#")) return "token-comment";
  if (value.startsWith('"') || value.startsWith("'")) return "token-string";
  if (/^\d/.test(value)) return "token-number";
  if (["True", "False", "None"].includes(value)) return "token-constant";
  return "token-keyword";
}

function appendHighlightedLine(container, sourceLine) {
  let offset = 0;
  for (const match of sourceLine.matchAll(pythonTokenPattern)) {
    container.append(document.createTextNode(sourceLine.slice(offset, match.index)));
    const token = document.createElement("span");
    token.className = tokenClass(match[0]);
    token.textContent = match[0];
    container.append(token);
    offset = match.index + match[0].length;
  }
  container.append(document.createTextNode(sourceLine.slice(offset)));
}

const codeSearchState = { matches: [], active: -1 };

function clearCodeSearchHighlights() {
  CSS.highlights?.delete("code-search-match");
  CSS.highlights?.delete("code-search-active");
  document.querySelectorAll(".code-line.search-match, .code-line.search-active").forEach((line) => {
    line.classList.remove("search-match", "search-active");
  });
  codeSearchState.matches = [];
  codeSearchState.active = -1;
}

function textRangeForOffsets(container, start, end) {
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  let offset = 0;
  let startNode;
  let startOffset;
  let endNode;
  let endOffset;
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const nextOffset = offset + node.textContent.length;
    if (!startNode && start >= offset && start < nextOffset) {
      startNode = node;
      startOffset = start - offset;
    }
    if (end > offset && end <= nextOffset) {
      endNode = node;
      endOffset = end - offset;
      break;
    }
    offset = nextOffset;
  }
  if (!startNode || !endNode) return null;
  const range = new Range();
  range.setStart(startNode, startOffset);
  range.setEnd(endNode, endOffset);
  return range;
}

function showCodeSearchMatch(index, { scroll = true } = {}) {
  if (!codeSearchState.matches.length) return;
  codeSearchState.active = (index + codeSearchState.matches.length) % codeSearchState.matches.length;
  const activeMatch = codeSearchState.matches[codeSearchState.active];
  document.querySelectorAll(".code-line.search-active").forEach((line) => line.classList.remove("search-active"));
  activeMatch.line.classList.add("search-active");
  if (CSS.highlights && globalThis.Highlight) CSS.highlights.set("code-search-active", new Highlight(activeMatch.range));
  document.querySelector("#code-search-count").textContent = `${codeSearchState.active + 1}/${codeSearchState.matches.length}`;
  if (scroll) activeMatch.line.scrollIntoView({ block: "center" });
}

function updateCodeSearch({ scroll = true } = {}) {
  clearCodeSearchHighlights();
  const query = document.querySelector("#code-search-input").value.trim().toLocaleLowerCase();
  const count = document.querySelector("#code-search-count");
  if (!query) {
    count.textContent = "0/0";
    document.querySelectorAll("#code-search-previous, #code-search-next, #code-search-clear").forEach((button) => { button.disabled = true; });
    return;
  }
  document.querySelectorAll("#code-content .line-code").forEach((lineCode) => {
    const text = lineCode.textContent;
    const searchableText = text.toLocaleLowerCase();
    let matchOffset = searchableText.indexOf(query);
    while (matchOffset !== -1) {
      const range = textRangeForOffsets(lineCode, matchOffset, matchOffset + query.length);
      if (range) codeSearchState.matches.push({ range, line: lineCode.closest(".code-line") });
      matchOffset = searchableText.indexOf(query, matchOffset + Math.max(query.length, 1));
    }
  });
  const enabled = codeSearchState.matches.length > 0;
  document.querySelectorAll("#code-search-previous, #code-search-next").forEach((button) => { button.disabled = !enabled; });
  document.querySelector("#code-search-clear").disabled = false;
  count.textContent = enabled ? `1/${codeSearchState.matches.length}` : "0/0";
  if (!enabled) return;
  codeSearchState.matches.forEach(({ line }) => line.classList.add("search-match"));
  if (CSS.highlights && globalThis.Highlight) CSS.highlights.set("code-search-match", new Highlight(...codeSearchState.matches.map(({ range }) => range)));
  showCodeSearchMatch(0, { scroll });
}

function setCodeSearchAvailable(available) {
  const search = document.querySelector("#code-search");
  const input = document.querySelector("#code-search-input");
  search.hidden = false;
  input.disabled = !available;
  if (!available) {
    input.value = "";
    updateCodeSearch({ scroll: false });
  }
}

function appendContractList(container, title, values, emptyText) {
  const section = document.createElement("section");
  section.className = "proposal-contract-section";
  const heading = document.createElement("h3");
  heading.textContent = title;
  section.append(heading);
  if (!values.length) {
    const empty = document.createElement("p");
    empty.className = "proposal-contract-muted";
    empty.textContent = emptyText;
    section.append(empty);
  } else {
    const list = document.createElement("ul");
    values.forEach((value) => {
      const item = document.createElement("li");
      item.textContent = value;
      list.append(item);
    });
    section.append(list);
  }
  container.append(section);
}

function renderProposalContract(node) {
  const contractApi = globalThis.HeroProposalContract;
  if (!contractApi) return;
  const normalized = contractApi.normalizeContractNode(node);
  const connections = contractApi.contractConnections(node.id, state.graph);
  const issues = contractApi.contractIssues(normalized, state.graph);
  const panel = document.querySelector("#proposal-contract");
  panel.replaceChildren();
  panel.hidden = false;
  document.querySelector("#code-content").hidden = true;
  document.querySelector("#code-empty").hidden = true;
  document.querySelector("#document-editor").hidden = true;
  document.querySelector("#code-kicker").textContent = "Proposal contract";
  document.querySelector("#code-title").textContent = normalized.label;
  document.querySelector("#code-meta").textContent = `${normalized.target_path || "No target path"} / proposed interface, not source code`;
  const statusElement = document.querySelector("#code-status");
  statusElement.className = `code-status ${normalized.status || "proposed"}`;
  statusElement.textContent = { proposed: "NEW", modified: "EDIT", accepted: "ACCEPTED" }[normalized.status] || "NEW";
  statusElement.hidden = false;
  setCodeSearchAvailable(false);

  const summary = document.createElement("section");
  summary.className = "proposal-contract-summary";
  const eyebrow = document.createElement("p");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = `${normalized.kind || "proposal"} · ${normalized.designProvenance || "HUMAN"}`;
  const responsibility = document.createElement("p");
  responsibility.textContent = normalized.designDescription || "No responsibility has been defined yet.";
  const metadata = document.createElement("dl");
  const metadataRows = [
    ["Target", normalized.target_path || "Not defined"],
    ["Qualified name", normalized.qualified_name || "Not defined"],
    ["Signature", normalized.signature || "Not defined"],
  ];
  if (normalized.realization?.status === "accepted") {
    metadataRows.push(["Accepted", `Task ${normalized.realization.task_id || ""} · ${normalized.realization.commit || "commit unavailable"}`]);
  }
  metadataRows.forEach(([termText, detailText]) => {
    const term = document.createElement("dt");
    term.textContent = termText;
    const detail = document.createElement("dd");
    detail.textContent = detailText;
    metadata.append(term, detail);
  });
  summary.append(eyebrow, responsibility, metadata);

  const interfaceSection = document.createElement("section");
  interfaceSection.className = "proposal-contract-section proposal-interface";
  const interfaceHeading = document.createElement("h3");
  interfaceHeading.textContent = normalized.status === "accepted" ? "Accepted contract" : "Proposed interface";
  const warning = document.createElement("p");
  warning.className = "proposal-preview-warning";
  warning.textContent = normalized.status === "accepted"
    ? "Accepted contract realization — the linked task passed verification and was recorded in Git."
    : "Virtual contract preview — no repository source has been created.";
  const preview = document.createElement("pre");
  const code = document.createElement("code");
  code.textContent = contractApi.interfacePreview(normalized, state.graph);
  preview.append(code);
  interfaceSection.append(interfaceHeading, warning, preview);

  panel.append(summary, interfaceSection);
  appendContractList(panel, "Requirements", normalized.satisfies, "No brief requirement linked yet.");
  appendContractList(panel, "Acceptance criteria", normalized.acceptance, "No behavioral acceptance criterion defined yet.");

  const connectionValues = connections.direct.map(({ node: endpoint, relation }) => {
    const direction = relation.direction === "outgoing" ? "→" : "←";
    return `${direction} ${endpoint.label} [${endpoint.status === "proposed" ? "proposed" : endpoint.status === "accepted" ? "accepted" : "observed"}] · ${relation.label}`;
  });
  appendContractList(panel, "Direct relationships", connectionValues, "No direct relationship defined.");
  const anchorValues = connections.observedAnchors.map(({ node: anchor, viaNode, relation }) =>
    `${anchor.label} (${anchor.source || anchor.kind}) via ${viaNode?.label || normalized.label} · ${relation.label}`
  );
  appendContractList(panel, "Observed implementation anchors", anchorValues, "No observed implementation anchor found for this proposal component.");

  const issueSection = document.createElement("section");
  issueSection.className = `proposal-contract-section proposal-readiness ${issues.length ? "incomplete" : "ready"}`;
  const issueHeading = document.createElement("h3");
  issueHeading.textContent = issues.length ? `Contract incomplete · ${issues.length}` : "Contract ready for design review";
  issueSection.append(issueHeading);
  if (issues.length) {
    const issueList = document.createElement("ul");
    issues.forEach((issue) => {
      const item = document.createElement("li");
      item.textContent = issue;
      issueList.append(item);
    });
    issueSection.append(issueList);
  } else {
    const ready = document.createElement("p");
    ready.textContent = "The structural draft is complete and connected. HARNESS approval and verification are still required.";
    issueSection.append(ready);
  }
  panel.append(issueSection);
}

function renderCodePanel(node = graphNode(state.selected)) {
  if (!node) return;
  dispatchEvent(new CustomEvent("code-selection-opened"));
  if (node.status === "proposed" || (!node.source && (node.designDescription || node.target_path || node.docstring))) {
    renderProposalContract(node);
    return;
  }
  if (!state.source) return;
  const source = state.source.sources?.[node.source] || (state.source.content ? state.source : null);
  if (!source) return;
  const status = node.status || "observed";
  const statusElement = document.querySelector("#code-status");
  statusElement.className = `code-status ${status}`;
  statusElement.textContent = { observed: "CODE", proposed: "NEW", modified: "EDIT", removed: "DELETE", accepted: "ACCEPTED" }[status];
  document.querySelector("#code-title").textContent = node.label;
  const content = document.querySelector("#code-content");
  const empty = document.querySelector("#code-empty");
  document.querySelector("#proposal-contract").hidden = true;
  document.querySelector("#code-kicker").textContent = "Code";
  content.replaceChildren();
  content.scrollTop = 0;
  const hasSource = node.line > 0 && node.end_line >= node.line;
  content.hidden = !hasSource;
  empty.hidden = hasSource;
  statusElement.hidden = false;
  setCodeSearchAvailable(hasSource);
  if (hasSource) {
    const qualifier = status === "observed" ? "Current source" : status === "accepted" ? "Current source; accepted contract realization" : "Current source; design change not applied";
    document.querySelector("#code-meta").textContent = `${node.source} / lines ${node.line}-${node.end_line} / ${qualifier}`;
    const sourceLines = source.content.split("\n");
    for (let lineNumber = node.line; lineNumber <= node.end_line; lineNumber += 1) {
      const row = document.createElement("div");
      row.className = "code-line";
      const number = document.createElement("span");
      number.className = "line-number";
      number.textContent = lineNumber;
      const code = document.createElement("code");
      code.className = "line-code";
      appendHighlightedLine(code, sourceLines[lineNumber - 1] || "");
      row.append(number, code);
      content.append(row);
    }
    updateCodeSearch({ scroll: false });
  } else {
    document.querySelector("#code-meta").textContent = `${node.source || state.source.source} / design only`;
  }
}

document.querySelector("#code-search-input").addEventListener("input", () => updateCodeSearch());
document.querySelector("#code-search-input").addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || !codeSearchState.matches.length) return;
  event.preventDefault();
  showCodeSearchMatch(codeSearchState.active + (event.shiftKey ? -1 : 1));
});
document.querySelector("#code-search-previous").addEventListener("click", () => showCodeSearchMatch(codeSearchState.active - 1));
document.querySelector("#code-search-next").addEventListener("click", () => showCodeSearchMatch(codeSearchState.active + 1));
document.querySelector("#code-search-clear").addEventListener("click", () => {
  const input = document.querySelector("#code-search-input");
  input.value = "";
  updateCodeSearch({ scroll: false });
  input.focus();
});
addEventListener("mission-document-opened", () => {
  document.querySelector("#code-search").hidden = true;
  document.querySelector("#proposal-contract").hidden = true;
  clearCodeSearchHighlights();
});
addEventListener("mission-document-closed", () => {
  setCodeSearchAvailable(!document.querySelector("#code-content").hidden);
});

const relationDialog = document.querySelector("#relation-dialog");
const relationForm = document.querySelector("#relation-form");

function nodeName(nodeId) {
  return state.graph.nodes.find((node) => node.id === nodeId)?.label || nodeId;
}

function propertiesText(properties) {
  return Object.entries(properties || {}).map(([key, value]) => `${key}=${value}`).join("\n");
}

function parseProperties(text) {
  const properties = {};
  for (const line of text.split("\n").map((value) => value.trim()).filter(Boolean)) {
    const separator = line.indexOf("=");
    if (separator <= 0) throw new Error(`Invalid property: ${line}`);
    const key = line.slice(0, separator).trim();
    const value = line.slice(separator + 1).trim();
    if (!key) throw new Error(`Invalid property: ${line}`);
    properties[key] = value;
  }
  return properties;
}

function revealAgentProposal(nodeId) {
  if (!nodeId || !graphNode(nodeId)) return false;
  expandTreePath(nodeId);
  if (state.view === "flow" && state.flowJourney.length) {
    state.flowJourney = [];
    state.flowEntryCandidate = null;
  }
  if (state.view !== "focus" && nodeId !== state.scope && !isDescendantOf(nodeId, state.scope)) {
    state.scope = state.graph.root || state.graph.nodes.find((node) => !node.parent)?.id;
    state.flowJourney = [];
    state.flowEntryCandidate = null;
  }
  if (state.view !== "focus" && isDescendantOf(nodeId, state.scope)) {
    let node = graphNode(nodeId);
    while (node?.parent && node.id !== state.scope) {
      state.inlineExpanded.add(node.parent);
      state.hiddenGraphNodes.delete(node.id);
      node = graphNode(node.parent);
    }
  }
  return navigationGraph().nodes.some((node) => node.id === nodeId);
}

function applyAgentGraphProposals(actions) {
  if (!state.graph || !Array.isArray(actions) || !actions.length) return { nodes: 0, relations: 0, replayed: 0, rejected: 0 };
  if (state.graphProjection) globalThis.HeroDiagrams?.restoreProjection();
  const previousSelection = state.selected;
  const allowedNodeKinds = new Set(["package", "module", "class", "function", "method"]);
  const allowedRelationKinds = new Set(["calls", "uses", "depends_on", "publishes", "contains", "custom"]);
  let nodes = 0;
  let relations = 0;
  let replayed = 0;
  let rejected = 0;
  let lastNodeId = null;

  actions.filter((action) => action?.op === "add_node").forEach((action) => {
    const parent = action.parent_id || null;
    const existing = action.node_id && state.graph.nodes.find((node) => node.id === action.node_id);
    if (existing) {
      if (existing.status === "proposed" && existing.label === action.label?.trim() && existing.kind === action.kind && (existing.parent || null) === parent) {
        lastNodeId = action.node_id;
        replayed += 1;
      } else rejected += 1;
      return;
    }
    if (!action.node_id || !action.label?.trim() || !allowedNodeKinds.has(action.kind) || (parent && !graphNode(parent))) {
      rejected += 1;
      return;
    }
    state.graph.nodes.push(globalThis.HeroProposalContract.normalizeContractNode({
      id: action.node_id,
      kind: action.kind,
      label: action.label.trim(),
      parent,
      line: 0,
      end_line: 0,
      source: "",
      status: "proposed",
      designDescription: action.description || "",
      target_path: action.target_path || "",
      qualified_name: action.qualified_name || "",
      signature: action.signature || "",
      docstring: action.docstring || "",
      satisfies: action.satisfies || [],
      acceptance: action.acceptance || [],
      designProvenance: "AGENT",
    }));
    if (parent) {
      state.graph.edges.push({ id: `containment:${crypto.randomUUID()}`, source: parent, target: action.node_id, kind: "contains", status: "proposed", properties: {}, generated: true, designProvenance: "AGENT" });
      state.treeExpanded.add(parent);
    }
    lastNodeId = action.node_id;
    nodes += 1;
    rebuildGraphIndexes();
  });

  actions.filter((action) => action?.op === "add_relation").forEach((action) => {
    const existing = action.relation_id && state.graph.edges.find((edge) => edge.id === action.relation_id);
    if (existing) {
      if (existing.status === "proposed" && existing.source === action.source_id && existing.target === action.target_id && existing.kind === action.kind) replayed += 1;
      else rejected += 1;
      return;
    }
    if (!action.relation_id || !allowedRelationKinds.has(action.kind) || action.source_id === action.target_id || !graphNode(action.source_id) || !graphNode(action.target_id)) {
      rejected += 1;
      return;
    }
    state.graph.edges.push({
      id: action.relation_id,
      source: action.source_id,
      target: action.target_id,
      kind: action.kind,
      label: action.label || "",
      properties: action.properties || {},
      status: "proposed",
      designProvenance: "AGENT",
    });
    relations += 1;
  });

  if (nodes || relations) {
    clearCallTrace();
    rebuildGraphIndexes();
    const proposalRendered = revealAgentProposal(lastNodeId);
    state.selected = lastNodeId ? (proposalRendered ? lastNodeId : previousSelection) : previousSelection;
    if (state.selected && !navigationGraph().nodes.some((node) => node.id === state.selected)) state.selected = null;
    state.selectedRelation = null;
    state.flowEntryCandidate = null;
    invalidateLayout();
    saveDesign();
    markGraphDesignChanged();
    updateTools();
    renderBreadcrumbs();
    render();
    syncTreeSelection();
    dispatchEvent(new CustomEvent("graph-selection-changed"));
    if (state.selected === lastNodeId) focusRenderedGraphNode(lastNodeId);
  }
  return { nodes, relations, replayed, rejected };
}

globalThis.applyAgentGraphProposals = applyAgentGraphProposals;

function openRelationDialog(mode, edge = null, sourceId = null, targetId = null) {
  const source = edge?.source || sourceId;
  const target = edge?.target || targetId;
  const edgeIds = edge ? edge.memberIds || [edge.id] : [];
  state.relationDraft = { mode, edgeIds, source, target };
  const grouped = edgeIds.length > 1;
  document.querySelector("#relation-dialog-title").textContent = mode === "add" ? "Add relationship" : grouped ? `Edit ${edgeIds.length} grouped relationships` : "Edit relationship";
  document.querySelector("#relation-source").textContent = nodeName(source);
  document.querySelector("#relation-target").textContent = nodeName(target);
  document.querySelector("#relation-name").value = edge ? edge.editLabel || relationText(edge) : "";
  document.querySelector("#relation-type").value = edge?.kind || "calls";
  document.querySelector("#relation-properties").value = propertiesText(edge?.properties);
  document.querySelector("#relation-properties").setCustomValidity("");
  const deleteButton = document.querySelector("#delete-relation");
  deleteButton.hidden = mode === "add";
  deleteButton.textContent = edge?.status === "removed" ? grouped ? "Restore relationships" : "Restore relationship" : grouped ? "Delete relationships" : "Delete relationship";
  relationDialog.showModal();
  document.querySelector("#relation-name").focus();
}

function deleteOrRestoreRelation() {
  const edgeIds = new Set(state.relationDraft?.edgeIds || []);
  const edges = state.graph.edges.filter((edge) => edgeIds.has(edge.id));
  if (!edges.length) return;
  const restoring = edges.every((edge) => edge.status === "removed");
  if (restoring) {
    edges.forEach((edge) => {
      edge.status = edge.previousStatus || "observed";
      delete edge.previousStatus;
    });
  } else {
    const proposedIds = new Set();
    edges.forEach((edge) => {
      if (edge.status === "proposed") proposedIds.add(edge.id);
      else {
        edge.previousStatus = edge.status;
        edge.status = "removed";
      }
    });
    state.graph.edges = state.graph.edges.filter((edge) => !proposedIds.has(edge.id));
  }
  relationDialog.close();
  state.relationDraft = null;
  state.selectedRelation = null;
  clearCallTrace();
  invalidateLayout();
  saveDesign();
  markGraphDesignChanged();
  render();
}

document.querySelector("#relation-close").addEventListener("click", () => relationDialog.close());
document.querySelector("#delete-relation").addEventListener("click", deleteOrRestoreRelation);
document.querySelector("#relation-properties").addEventListener("input", (event) => event.target.setCustomValidity(""));
relationForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const propertiesField = document.querySelector("#relation-properties");
  let properties;
  try {
    properties = parseProperties(propertiesField.value);
  } catch (error) {
    propertiesField.setCustomValidity(error.message);
    propertiesField.reportValidity();
    return;
  }
  const label = document.querySelector("#relation-name").value.trim();
  const kind = document.querySelector("#relation-type").value;
  if (state.relationDraft.mode === "add") {
    state.graph.edges.push({
      id: `relation:${crypto.randomUUID()}`,
      source: state.relationDraft.source,
      target: state.relationDraft.target,
      kind,
      label,
      properties,
      status: "proposed",
    });
  } else {
    const edgeIds = new Set(state.relationDraft.edgeIds);
    state.graph.edges.filter((edge) => edgeIds.has(edge.id)).forEach((edge) => {
      edge.label = label;
      edge.kind = kind;
      edge.properties = properties;
      if (["observed", "accepted"].includes(edge.status)) edge.status = "modified";
    });
  }
  relationDialog.close();
  state.relationDraft = null;
  state.selectedRelation = null;
  clearCallTrace();
  invalidateLayout();
  saveDesign();
  markGraphDesignChanged();
  render();
});

const nodeDialog = document.querySelector("#node-dialog");
const nodeForm = document.querySelector("#node-form");

function populateParents(excludedId = null) {
  const parentSelect = document.querySelector("#node-parent");
  parentSelect.replaceChildren();
  const rootOption = document.createElement("option");
  rootOption.value = ""; rootOption.textContent = "Graph root"; parentSelect.append(rootOption);
  state.graph.nodes.filter((node) => node.id !== excludedId && node.status !== "removed").forEach((node) => {
    const option = document.createElement("option");
    option.value = node.id; option.textContent = `${node.label} (${node.kind})`; parentSelect.append(option);
  });
}

function openNodeDialog(mode) {
  const node = state.graph.nodes.find((candidate) => candidate.id === state.selected);
  nodeForm.dataset.mode = mode;
  populateParents(mode === "edit" ? node.id : null);
  document.querySelector("#node-dialog-title").textContent = mode === "add" ? "Add proposed node" : "Edit as proposal";
  document.querySelector("#node-name").value = mode === "edit" ? node.label : "";
  document.querySelector("#node-type").value = mode === "edit" ? node.kind : "class";
  document.querySelector("#node-parent").value = mode === "edit" ? node.parent || "" : node && node.status !== "removed" ? node.id : state.scope;
  const contract = globalThis.HeroProposalContract.normalizeContractNode(mode === "edit" ? node : {});
  document.querySelector("#node-target-path").value = contract.target_path;
  document.querySelector("#node-qualified-name").value = contract.qualified_name;
  document.querySelector("#node-signature").value = contract.signature;
  document.querySelector("#node-description").value = contract.designDescription;
  document.querySelector("#node-docstring").value = contract.docstring;
  document.querySelector("#node-satisfies").value = contract.satisfies.join("\n");
  document.querySelector("#node-acceptance").value = contract.acceptance.join("\n");
  nodeDialog.showModal();
  document.querySelector("#node-name").focus();
}

function removeOrRestoreSelected() {
  const node = state.graph.nodes.find((candidate) => candidate.id === state.selected);
  if (!node) return;
  if (node.status === "removed") {
    clearCallTrace();
    node.status = node.previousStatus || "observed";
    delete node.previousStatus;
  } else if (node.status === "proposed") {
    const removedNodeIds = descendantIds(node.id);
    removedNodeIds.add(node.id);
    const nonProposedDescendants = [...removedNodeIds]
      .map((nodeId) => graphNode(nodeId))
      .filter((candidate) => candidate && candidate.status !== "proposed");
    if (nonProposedDescendants.length) {
      document.querySelector("#design-sync-status").textContent = "Cannot delete: proposal contains non-proposed nodes";
      return;
    }
    clearCallTrace();
    state.graph.nodes = state.graph.nodes.filter((candidate) => !removedNodeIds.has(candidate.id));
    state.graph.edges = state.graph.edges.filter((edge) => !removedNodeIds.has(edge.source) && !removedNodeIds.has(edge.target));
    rebuildGraphIndexes();
    state.flowJourney = flowNavigation.pruneJourney(state.flowJourney, removedNodeIds);
    state.flowEntryCandidate = null;
    removedNodeIds.forEach((nodeId) => {
      delete state.positions[nodeId];
      state.inlineExpanded.delete(nodeId);
      state.hiddenGraphNodes.delete(nodeId);
      state.treeExpanded.delete(nodeId);
    });
    state.selected = null;
  } else {
    clearCallTrace();
    node.previousStatus = node.status;
    node.status = "removed";
  }
  invalidateLayout();
  saveDesign(); markGraphDesignChanged(); renderBreadcrumbs(); updateTools(); render(); syncTreeSelection();
  dispatchEvent(new CustomEvent("graph-selection-changed"));
}

document.querySelector("#edit-node").addEventListener("click", () => openNodeDialog("edit"));
document.querySelector("#node-close").addEventListener("click", () => nodeDialog.close());
document.querySelector("#reset-design").addEventListener("click", () => {
  localStorage.removeItem(DESIGN_STORAGE_KEY);
  state.graph = structuredClone(state.baseGraph);
  rebuildGraphIndexes();
  state.positions = {};
  state.inlineExpanded.clear();
  state.flowJourney = [];
  state.flowEntryCandidate = null;
  state.hiddenGraphNodes.clear();
  state.onlyHighlighted = false;
  state.callTrace = null;
  state.scope = state.graph.root || state.graph.nodes.find((node) => !node.parent)?.id;
  state.treeExpanded = new Set(state.graph.nodes.filter((node) => node.kind === "package").map((node) => node.id));
  state.selected = null;
  state.selectedRelation = null;
  invalidateLayout();
  markGraphDesignChanged();
  renderFileTree(); renderBreadcrumbs(); updateGraphCount(); updateTools(); render();
});
nodeForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const mode = nodeForm.dataset.mode;
  const name = document.querySelector("#node-name").value.trim();
  const kind = document.querySelector("#node-type").value;
  const parent = document.querySelector("#node-parent").value || null;
  const contract = globalThis.HeroProposalContract.normalizeContractNode({
    target_path: document.querySelector("#node-target-path").value,
    qualified_name: document.querySelector("#node-qualified-name").value,
    signature: document.querySelector("#node-signature").value,
    designDescription: document.querySelector("#node-description").value,
    docstring: document.querySelector("#node-docstring").value,
    satisfies: document.querySelector("#node-satisfies").value,
    acceptance: document.querySelector("#node-acceptance").value,
  });
  clearCallTrace();
  if (mode === "add") {
    const nodeId = `proposal:${crypto.randomUUID()}`;
    state.graph.nodes.push({ ...contract, id: nodeId, kind, label: name, parent, line: 0, end_line: 0, source: "", status: "proposed", designProvenance: "HUMAN" });
    if (parent) state.graph.edges.push({ id: `containment:${crypto.randomUUID()}`, source: parent, target: nodeId, kind: "contains", status: "proposed", properties: {}, generated: true });
    state.selected = nodeId;
  } else {
    const node = state.graph.nodes.find((candidate) => candidate.id === state.selected);
    Object.assign(node, contract, { label: name, kind, parent });
    if (["observed", "accepted"].includes(node.status)) node.status = "modified";
    state.graph.edges = state.graph.edges.filter((edge) => !(edge.kind === "contains" && edge.target === node.id));
    if (parent) state.graph.edges.push({ id: `containment:${crypto.randomUUID()}`, source: parent, target: node.id, kind: "contains", status: node.status === "proposed" ? "proposed" : "modified", properties: {}, generated: true });
  }
  rebuildGraphIndexes();
  revealAgentProposal(state.selected);
  invalidateLayout();
  nodeDialog.close(); saveDesign(); markGraphDesignChanged(); renderBreadcrumbs(); refreshSelection();
});

const dialog = document.querySelector("#feedback-dialog");
document.querySelector("#feedback-toggle").addEventListener("click", () => dialog.showModal());
document.querySelector("#feedback-close").addEventListener("click", () => dialog.close());
document.querySelector("#friction").addEventListener("input", (event) => { document.querySelector("#friction-value").textContent = event.target.value; });
document.querySelector("#feedback-form").addEventListener("submit", async (event) => {
  event.preventDefault(); const status = document.querySelector("#form-status"); status.textContent = "Saving...";
  const payload = { view: state.view, task: state.task, friction: Number(document.querySelector("#friction").value), decision: document.querySelector("#decision").value, notes: document.querySelector("#notes").value };
  try {
    const response = await fetch("/api/observations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    if (!response.ok) throw new Error((await response.json()).error);
    event.target.reset(); document.querySelector("#friction-value").textContent = "3"; status.textContent = ""; dialog.close();
  } catch (error) { status.textContent = error.message || "Could not save the finding."; }
});
globalThis.HeroArchitectureScenarios?.install(() => state.graph);
loadExperiment();
