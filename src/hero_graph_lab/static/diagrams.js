(() => {
  const dialog = document.querySelector("#diagram-dialog");
  const projectionDialog = document.querySelector("#projection-dialog");
  const projectionForm = document.querySelector("#projection-form");
  const projectionCreateDepthSelect = document.querySelector("#projection-depth");
  const projectionCreateButton = document.querySelector("#projection-open");
  const projectionCreateStatus = document.querySelector("#projection-status");
  const typeSelect = document.querySelector("#diagram-type");
  const depthSelect = document.querySelector("#diagram-depth");
  const projectionDepthSelect = document.querySelector("#graph-projection-depth");
  const fromSelect = document.querySelector("#diagram-path-from");
  const toSelect = document.querySelector("#diagram-path-to");
  const pathControls = document.querySelector("#diagram-path-controls");
  const generateButton = document.querySelector("#diagram-generate");
  const sourceField = document.querySelector("#diagram-source");
  const preview = document.querySelector("#diagram-preview");
  const status = document.querySelector("#diagram-status");
  const confidence = document.querySelector("#diagram-confidence");
  const inferredCache = new Map();
  const MAX_DIAGRAM_NODES = 90;
  let pendingProjection = null;

  function selectedNode() {
    return state.graph?.nodes.find((node) => node.id === state.selected) || null;
  }

  function contextNode(options = {}) {
    return options.anchorId ? state.graph?.nodes.find((node) => node.id === options.anchorId) || null : selectedNode();
  }

  function nodes() {
    return state.graph.nodes.filter((node) => node.status !== "removed");
  }

  function edges() {
    return state.graph.edges.filter((edge) => edge.status !== "removed");
  }

  function nodeMap() {
    return new Map(nodes().map((node) => [node.id, node]));
  }

  function childrenMap(kinds = null) {
    const result = new Map();
    nodes().forEach((node) => {
      if (!node.parent || (kinds && !kinds.has(node.kind))) return;
      if (!result.has(node.parent)) result.set(node.parent, []);
      result.get(node.parent).push(node);
    });
    result.forEach((children) => children.sort((left, right) => left.id.localeCompare(right.id)));
    return result;
  }

  function ancestor(nodeId, kinds) {
    const byId = nodeMap();
    let node = byId.get(nodeId);
    while (node) {
      if (kinds.has(node.kind)) return node;
      node = byId.get(node.parent);
    }
    return null;
  }

  function isWithin(nodeId, ancestorId) {
    const byId = nodeMap();
    let node = byId.get(nodeId);
    while (node) {
      if (node.id === ancestorId) return true;
      node = byId.get(node.parent);
    }
    return false;
  }

  function safe(value) {
    return String(value || "").replace(/["\[\]{}()<>|#;]/g, " ").replace(/\s+/g, " ").trim();
  }

  function nodeLabel(node) {
    const statusLabel = node.status && node.status !== "observed" ? ` / ${node.status.toUpperCase()}` : "";
    return `${safe(node.label)} / ${safe(node.kind)}${statusLabel}`;
  }

  function ensureSize(diagramNodes) {
    if (!diagramNodes.length) throw new Error("No graph elements match this diagram and selection.");
    if (diagramNodes.length > MAX_DIAGRAM_NODES) {
      throw new Error(`This projection contains ${diagramNodes.length} nodes. Reduce depth or narrow the selection (limit ${MAX_DIAGRAM_NODES}).`);
    }
  }

  function flowchart(diagramNodes, diagramEdges, { selectedIds = new Set(), direction = "LR" } = {}) {
    const orderedNodes = [...diagramNodes].sort((left, right) => left.id.localeCompare(right.id));
    ensureSize(orderedNodes);
    const aliases = new Map(orderedNodes.map((node, index) => [node.id, `n${index}`]));
    const lines = [`flowchart ${direction}`];
    orderedNodes.forEach((node) => lines.push(`  ${aliases.get(node.id)}["${nodeLabel(node)}"]`));
    [...diagramEdges]
      .filter((edge) => aliases.has(edge.source) && aliases.has(edge.target))
      .sort((left, right) => `${left.source}|${left.target}|${left.kind}`.localeCompare(`${right.source}|${right.target}|${right.kind}`))
      .forEach((edge) => {
        const statusLabel = edge.status && edge.status !== "observed" ? ` / ${edge.status.toUpperCase()}` : "";
        const label = safe(edge.diagramLabel || edge.label || edge.kind) + statusLabel;
        const arrow = edge.kind === "contains" ? "-.->" : "-->";
        lines.push(`  ${aliases.get(edge.source)} ${arrow}|${label}| ${aliases.get(edge.target)}`);
      });
    lines.push("  classDef selected stroke:#18201d,stroke-width:4px", "  classDef proposed stroke:#176b57,stroke-width:3px,stroke-dasharray:6 4", "  classDef modified stroke:#397d96,stroke-width:3px");
    const selectedAliases = [...selectedIds].filter((id) => aliases.has(id)).map((id) => aliases.get(id));
    if (selectedAliases.length) lines.push(`  class ${selectedAliases.join(",")} selected`);
    const proposed = orderedNodes.filter((node) => node.status === "proposed").map((node) => aliases.get(node.id));
    const modified = orderedNodes.filter((node) => node.status === "modified").map((node) => aliases.get(node.id));
    if (proposed.length) lines.push(`  class ${proposed.join(",")} proposed`);
    if (modified.length) lines.push(`  class ${modified.join(",")} modified`);
    return lines.join("\n");
  }

  function hierarchyDiagram(depth, options = {}) {
    const current = contextNode(options);
    const selectedPackage = current?.kind === "package" ? current : current ? ancestor(current.id, new Set(["package"])) : null;
    const scopePackage = state.scope ? ancestor(state.scope, new Set(["package"])) : null;
    const root = selectedPackage || scopePackage || nodeMap().get(state.graph.root) || nodes().find((node) => node.kind === "package");
    if (!root) throw new Error("The graph has no package hierarchy.");
    const children = childrenMap(new Set(["package", "module"]));
    const included = new Map([[root.id, root]]);
    const queue = [{ id: root.id, level: 0 }];
    while (queue.length) {
      const item = queue.shift();
      if (item.level >= depth) continue;
      (children.get(item.id) || []).forEach((child) => {
        included.set(child.id, child);
        queue.push({ id: child.id, level: item.level + 1 });
      });
    }
    const hierarchyEdges = edges().filter((edge) => edge.kind === "contains" && included.has(edge.source) && included.has(edge.target));
    return {
      title: `Package hierarchy / ${root.label}`,
      summary: `${included.size} package or module nodes through containment depth ${depth}.`,
      source: flowchart([...included.values()], hierarchyEdges, { selectedIds: new Set([root.id]), direction: "TB" }),
      graph: { nodes: [...included.values()], edges: hierarchyEdges },
    };
  }

  function classFor(nodeId) {
    return ancestor(nodeId, new Set(["class"]));
  }

  function classDependencies() {
    const byPair = new Map();
    edges().filter((edge) => edge.kind === "calls").forEach((edge) => {
      const sourceClass = classFor(edge.source);
      const targetClass = classFor(edge.target);
      if (!sourceClass || !targetClass || sourceClass.id === targetClass.id) return;
      const key = `${sourceClass.id}|${targetClass.id}`;
      const dependency = byPair.get(key) || { id: `class-dependency:${key}`, source: sourceClass.id, target: targetClass.id, kind: "calls", count: 0, statuses: new Set(), memberIds: [] };
      dependency.count += 1;
      dependency.statuses.add(edge.status || "observed");
      dependency.memberIds.push(edge.id);
      byPair.set(key, dependency);
    });
    return [...byPair.values()].map((dependency) => ({
      ...dependency,
      status: dependency.statuses.size === 1 ? [...dependency.statuses][0] : "modified",
      diagramLabel: `calls x${dependency.count}`,
    }));
  }

  function classDiagram(depth, options = {}) {
    const current = contextNode(options);
    const root = current ? classFor(current.id) : null;
    if (!root) throw new Error("Select a class or one of its methods to build a class diagram.");
    const dependencies = classDependencies();
    const included = new Set([root.id]);
    let frontier = new Set([root.id]);
    for (let level = 0; level < depth && frontier.size; level += 1) {
      const next = new Set();
      dependencies.forEach((edge) => {
        if (frontier.has(edge.source) && !included.has(edge.target)) next.add(edge.target);
        if (frontier.has(edge.target) && !included.has(edge.source)) next.add(edge.source);
      });
      next.forEach((id) => included.add(id));
      frontier = next;
    }
    const classNodes = nodes().filter((node) => included.has(node.id));
    ensureSize(classNodes);
    const aliases = new Map(classNodes.sort((left, right) => left.id.localeCompare(right.id)).map((node, index) => [node.id, `C${index}`]));
    const children = childrenMap(new Set(["method"]));
    const lines = ["classDiagram"];
    classNodes.forEach((node) => {
      lines.push(`  class ${aliases.get(node.id)}["${safe(node.label)}"] {`);
      (children.get(node.id) || []).forEach((method) => lines.push(`    +${safe(method.label)}()`));
      lines.push("  }");
    });
    const includedDependencies = dependencies.filter((edge) => included.has(edge.source) && included.has(edge.target));
    includedDependencies.forEach((edge) => {
      const statusLabel = edge.statuses.size === 1 && edge.statuses.has("observed") ? "" : ` / ${[...edge.statuses].join("+").toUpperCase()}`;
      lines.push(`  ${aliases.get(edge.source)} --> ${aliases.get(edge.target)} : calls x${edge.count}${statusLabel}`);
    });
    lines.push("  classDef selected stroke:#18201d,stroke-width:4px", `  cssClass "${aliases.get(root.id)}" selected`);
    return {
      title: `Class diagram / ${root.label}`,
      summary: `${classNodes.length} classes connected by current method-call dependencies; design proposals retain their status and no inheritance is inferred.`,
      source: lines.join("\n"),
      graph: { nodes: classNodes, edges: includedDependencies },
    };
  }

  function callDiagram(depth, options = {}) {
    const root = contextNode(options);
    if (!root || !["function", "method"].includes(root.kind)) throw new Error("Select a function or method to build a call graph.");
    const callEdges = edges().filter((edge) => edge.kind === "calls");
    const included = new Set([root.id]);
    let frontier = new Set([root.id]);
    const includedEdges = new Map();
    for (let level = 0; level < depth && frontier.size; level += 1) {
      const next = new Set();
      callEdges.forEach((edge) => {
        if (!frontier.has(edge.source)) return;
        includedEdges.set(edge.id, edge);
        if (!included.has(edge.target)) next.add(edge.target);
        included.add(edge.target);
      });
      frontier = next;
    }
    const callNodes = nodes().filter((node) => included.has(node.id));
    return {
      title: `Call graph / ${root.label}`,
      summary: `${callNodes.length} callable nodes through outgoing call depth ${depth}. Call order is not represented.`,
      source: flowchart(callNodes, [...includedEdges.values()], { selectedIds: new Set([root.id]) }),
      graph: { nodes: callNodes, edges: [...includedEdges.values()] },
    };
  }

  function moduleFor(nodeId) {
    return ancestor(nodeId, new Set(["module"]));
  }

  function moduleDependencies() {
    const byPair = new Map();
    edges().filter((edge) => edge.kind !== "contains").forEach((edge) => {
      const sourceModule = moduleFor(edge.source);
      const targetModule = moduleFor(edge.target);
      if (!sourceModule || !targetModule || sourceModule.id === targetModule.id) return;
      const key = `${sourceModule.id}|${targetModule.id}|${edge.kind}`;
      const dependency = byPair.get(key) || { id: `module-dependency:${key}`, source: sourceModule.id, target: targetModule.id, kind: edge.kind, status: "observed", statuses: new Set(), count: 0 };
      dependency.count += 1;
      dependency.statuses.add(edge.status || "observed");
      dependency.status = dependency.statuses.size === 1 ? [...dependency.statuses][0] : "modified";
      dependency.memberIds ||= [];
      dependency.memberIds.push(edge.id);
      dependency.diagramLabel = `${edge.kind} x${dependency.count}`;
      byPair.set(key, dependency);
    });
    return [...byPair.values()];
  }

  function moduleDiagram(depth, options = {}) {
    const current = contextNode(options);
    const rootModule = current ? moduleFor(current.id) : null;
    const rootPackage = current ? ancestor(current.id, new Set(["package"])) : state.scope ? ancestor(state.scope, new Set(["package"])) : null;
    const dependencies = moduleDependencies();
    const included = new Set();
    if (rootModule) included.add(rootModule.id);
    else {
      nodes().filter((node) => node.kind === "module" && (!rootPackage || isWithin(node.id, rootPackage.id))).forEach((node) => included.add(node.id));
    }
    if (rootModule) {
      let frontier = new Set([rootModule.id]);
      for (let level = 0; level < depth && frontier.size; level += 1) {
        const next = new Set();
        dependencies.forEach((edge) => {
          if (frontier.has(edge.source) && !included.has(edge.target)) next.add(edge.target);
          if (frontier.has(edge.target) && !included.has(edge.source)) next.add(edge.source);
        });
        next.forEach((id) => included.add(id));
        frontier = next;
      }
    }
    const moduleNodes = nodes().filter((node) => included.has(node.id));
    const moduleEdges = dependencies.filter((edge) => included.has(edge.source) && included.has(edge.target));
    return {
      title: `Module dependencies / ${rootModule?.label || rootPackage?.label || state.graph.source}`,
      summary: `${moduleNodes.length} modules; cross-module dependencies aggregate extracted graph relations.`,
      source: flowchart(moduleNodes, moduleEdges, { selectedIds: new Set(rootModule ? [rootModule.id] : []) }),
      graph: { nodes: moduleNodes, edges: moduleEdges },
    };
  }

  function neighborhoodDiagram(depth, options = {}) {
    const root = contextNode(options);
    if (!root) throw new Error("Select a node to build its neighborhood.");
    const graphEdges = edges();
    const included = new Set([root.id]);
    let frontier = new Set([root.id]);
    for (let level = 0; level < depth && frontier.size; level += 1) {
      const next = new Set();
      graphEdges.forEach((edge) => {
        if (frontier.has(edge.source) && !included.has(edge.target)) next.add(edge.target);
        if (frontier.has(edge.target) && !included.has(edge.source)) next.add(edge.source);
      });
      next.forEach((id) => included.add(id));
      frontier = next;
    }
    const diagramNodes = nodes().filter((node) => included.has(node.id));
    const diagramEdges = graphEdges.filter((edge) => included.has(edge.source) && included.has(edge.target));
    return {
      title: `Neighborhood / ${root.label}`,
      summary: `${diagramNodes.length} nodes within undirected graph distance ${depth}.`,
      source: flowchart(diagramNodes, diagramEdges, { selectedIds: new Set([root.id]) }),
      graph: { nodes: diagramNodes, edges: diagramEdges },
    };
  }

  function shortestPath(fromId, toId, maxDepth) {
    const graphEdges = edges();
    const visited = new Set([fromId]);
    const previous = new Map();
    const queue = [{ id: fromId, depth: 0 }];
    while (queue.length) {
      const current = queue.shift();
      if (current.id === toId) break;
      if (current.depth >= maxDepth) continue;
      graphEdges.forEach((edge) => {
        let neighbor = null;
        if (edge.source === current.id) neighbor = edge.target;
        else if (edge.target === current.id) neighbor = edge.source;
        if (!neighbor || visited.has(neighbor)) return;
        visited.add(neighbor);
        previous.set(neighbor, { nodeId: current.id, edge });
        queue.push({ id: neighbor, depth: current.depth + 1 });
      });
    }
    if (!visited.has(toId)) return null;
    const pathNodeIds = [toId];
    const pathEdges = [];
    let cursor = toId;
    while (cursor !== fromId) {
      const step = previous.get(cursor);
      if (!step) return null;
      pathEdges.unshift(step.edge);
      cursor = step.nodeId;
      pathNodeIds.unshift(cursor);
    }
    return { pathNodeIds, pathEdges };
  }

  function pathDiagram(depth, options = {}) {
    const fromId = options.fromId || fromSelect.value;
    const toId = options.toId || toSelect.value;
    if (!fromId || !toId || fromId === toId) throw new Error("Choose two different pinned nodes.");
    const path = shortestPath(fromId, toId, depth);
    if (!path) throw new Error(`No path was found between the pinned nodes within depth ${depth}.`);
    const byId = nodeMap();
    const pathNodes = path.pathNodeIds.map((id) => byId.get(id)).filter(Boolean);
    return {
      title: `Pinned path / ${byId.get(fromId)?.label} to ${byId.get(toId)?.label}`,
      summary: `Shortest undirected graph path with ${path.pathEdges.length} relationships; arrows retain their extracted direction.`,
      source: flowchart(pathNodes, path.pathEdges, { selectedIds: new Set([fromId, toId]) }),
      graph: { nodes: pathNodes, edges: path.pathEdges },
    };
  }

  function compactInferenceContext(depth) {
    const seedIds = new Set([...exploreState.pinnedNodeIds]);
    if (state.selected) seedIds.add(state.selected);
    const visibleIds = new Set(seedIds);
    let frontier = new Set(seedIds);
    const graphEdges = edges();
    for (let level = 0; level < Math.min(depth, 2) && frontier.size; level += 1) {
      const next = new Set();
      graphEdges.forEach((edge) => {
        if (frontier.has(edge.source) && !visibleIds.has(edge.target)) next.add(edge.target);
        if (frontier.has(edge.target) && !visibleIds.has(edge.source)) next.add(edge.source);
      });
      next.forEach((id) => visibleIds.add(id));
      frontier = next;
    }
    const selected = selectedNode();
    return {
      selectedNodeId: selected?.id || null,
      selectedRelationId: null,
      scopeId: state.scope || null,
      visibleNodeIds: [...visibleIds].slice(0, MAX_DIAGRAM_NODES),
      pinnedNodeIds: [...exploreState.pinnedNodeIds],
      visibleSource: selected?.source ? { path: selected.source, startLine: selected.line || 1, endLine: selected.end_line || selected.line || 1 } : null,
    };
  }

  function inferencePrompt(depth) {
    const byId = nodeMap();
    const selected = selectedNode();
    const pins = [...exploreState.pinnedNodeIds].map((id) => byId.get(id)).filter(Boolean);
    const anchors = [selected, ...pins].filter(Boolean).map((node) => `${node.kind} ${node.label} (${node.id})`).join("; ");
    return `Genera un diagrama Mermaid sequenceDiagram sobre el flujo de negocio plausible alrededor de estos elementos: ${anchors}. Usa únicamente interacciones con flechas dirigidas que indiquen claramente emisor y receptor. Usa únicamente el contexto acotado y las herramientas de lectura necesarias. Profundidad conceptual máxima: ${depth}. Responde en español con una breve lista de supuestos y un único bloque Mermaid. Marca el resultado como INFERRED. El extractor conserva relaciones calls pero no el orden de las llamadas: no presentes la secuencia como determinista ni inventes identificadores o locators. No escribas archivos ni propongas operaciones de edición.`;
  }

  function graphSignature(visibleIds) {
    const included = new Set(visibleIds);
    return JSON.stringify({
      nodes: nodes().filter((node) => included.has(node.id)).map((node) => [node.id, node.kind, node.label, node.status || "observed"]),
      edges: edges().filter((edge) => included.has(edge.source) || included.has(edge.target)).map((edge) => [edge.id, edge.source, edge.target, edge.kind, edge.status || "observed"]),
    });
  }

  async function inferredSequence(depth) {
    if (!state.selected && exploreState.pinnedNodeIds.size < 1) throw new Error("Select or pin at least one node for an inferred sequence.");
    if (!exploreState.sessionId) throw new Error("Explore is not connected to a model provider.");
    const context = compactInferenceContext(depth);
    const cacheKey = JSON.stringify({ source: state.graph.source, selected: state.selected, pins: [...exploreState.pinnedNodeIds], depth, promptVersion: 1, graph: graphSignature(context.visibleNodeIds) });
    let answer = inferredCache.get(cacheKey);
    let cached = true;
    if (!answer) {
      cached = false;
      answer = await submitExplorePrompt(inferencePrompt(depth), context);
      if (!answer) throw new Error(document.querySelector("#chat-status").textContent || "The model did not return a sequence diagram.");
      inferredCache.set(cacheKey, answer);
    }
    const mermaid = answer.match(/```mermaid\s*([\s\S]*?)```/i)?.[1]?.trim() || "";
    return {
      title: "Business sequence / semantic interpretation",
      summary: `${cached ? "Cached. " : ""}Model-inferred sequence; call order is not available in the AST graph.`,
      source: mermaid,
      markdown: `> **INFERRED** — semantic hypothesis. The AST graph does not preserve call order.\n\n${answer}`,
      inferred: true,
    };
  }

  function normalizedProjectionGraph(graph) {
    return {
      nodes: graph.nodes.map((node) => ({ ...node, context: false })),
      edges: graph.edges.map((edge) => ({
        ...edge,
        id: edge.id || `projection:${edge.source}:${edge.kind}:${edge.target}`,
        memberIds: edge.memberIds || [edge.id],
        aggregate: Boolean(edge.aggregate || edge.memberIds?.length > 1),
      })),
    };
  }

  function captureInteractiveView() {
    return {
      view: state.view,
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
  }

  function setProjectionView(view, label) {
    state.view = view;
    document.querySelectorAll("[data-graph-view]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.graphView === view));
    });
    document.querySelector("#graph-view-label").textContent = `${label} / ${view === "focus" ? "Focus" : "Flow"}`;
  }

  function renderProjectionBar() {
    const bar = document.querySelector("#graph-projection-bar");
    const projection = state.graphProjection;
    bar.hidden = !projection;
    if (!projection) return;
    document.querySelector("#graph-projection-title").textContent = projection.label;
    document.querySelector("#graph-projection-meta").textContent = `${projection.graph.nodes.length} nodes / depth ${projection.depth} / ${projection.history.length + 1} step${projection.history.length ? "s" : ""}`;
    projectionDepthSelect.value = String(projection.depth);
    document.querySelector("#graph-projection-back").disabled = !projection.history.length;
  }

  function projectionDefinition(type) {
    return definitions.find((item) => item.id === type);
  }

  function recommendedProjection() {
    const current = selectedNode();
    if (!current && exploreState.pinnedNodeIds.size >= 2) {
      const [fromId, toId] = [...exploreState.pinnedNodeIds];
      return { type: "path", view: "focus", label: "Pinned path", options: { fromId, toId } };
    }
    if (!current) throw new Error("Select a node or pin two nodes to create a graph projection.");
    if (current.kind === "package") return { type: "hierarchy", view: "flow", label: "Package hierarchy", options: { anchorId: current.id } };
    if (current.kind === "module") return { type: "neighborhood", view: "flow", label: "Module neighborhood", options: { anchorId: current.id } };
    if (current.kind === "class") return { type: "classes", view: "focus", label: "Class collaborators", options: { anchorId: current.id } };
    if (["function", "method"].includes(current.kind)) return { type: "calls", view: "flow", label: "Call graph", options: { anchorId: current.id } };
    return { type: "neighborhood", view: "focus", label: "Selection neighborhood", options: { anchorId: current.id } };
  }

  function activateProjection(recommendation) {
    if (state.callTrace) clearCallTrace();
    const item = projectionDefinition(recommendation.type);
    const depth = Number(depthSelect.value);
    const result = item.generate(depth, recommendation.options);
    state.graphProjection = {
      type: recommendation.type,
      label: recommendation.label,
      view: recommendation.view,
      options: recommendation.options,
      depth,
      graph: normalizedProjectionGraph(result.graph),
      history: [],
      activeAnchor: state.selected,
      savedLayout: null,
      returnView: captureInteractiveView(),
    };
    state.positions = {};
    state.currentLayout = null;
    state.selectedRelation = null;
    releaseGraphLayout();
    setProjectionView(recommendation.view, recommendation.label);
    renderProjectionBar();
    updateGraphCount();
    updateTools();
    render();
    fitGraphToView();
    document.querySelector("#graph-command-status").textContent = `${recommendation.label} opened. Select a node and press G, E, or double-click to expand it.`;
    dispatchEvent(new CustomEvent("graph-selection-changed"));
  }

  function containmentExpansion(anchorId) {
    const byId = nodeMap();
    const anchor = byId.get(anchorId);
    if (!anchor) throw new Error("The selected node is no longer available.");
    const childNodes = nodes().filter((node) => node.parent === anchorId);
    const nodeIds = new Set([anchorId, ...childNodes.map((node) => node.id)]);
    return {
      nodes: [anchor, ...childNodes],
      edges: edges().filter((edge) => edge.kind === "contains" && nodeIds.has(edge.source) && nodeIds.has(edge.target)),
    };
  }

  function classExpansion(anchorId) {
    const result = classDiagram(state.graphProjection?.depth || 1, { anchorId });
    const root = classFor(anchorId);
    if (!root) return result.graph;
    const methods = nodes().filter((node) => node.parent === root.id && node.kind === "method");
    const nodeIds = new Set([root.id, ...methods.map((node) => node.id)]);
    const containment = edges().filter((edge) => edge.kind === "contains" && nodeIds.has(edge.source) && nodeIds.has(edge.target));
    return {
      nodes: [...result.graph.nodes, ...methods],
      edges: [...result.graph.edges, ...containment],
    };
  }

  function expansionGraph(projection, anchorId) {
    if (projection.type === "hierarchy") return containmentExpansion(anchorId);
    if (projection.type === "classes") return classExpansion(anchorId);
    if (projection.type === "path") return neighborhoodDiagram(projection.depth, { anchorId }).graph;
    return projectionDefinition(projection.type).generate(projection.depth, { ...projection.options, anchorId }).graph;
  }

  function setProjectionDepth() {
    const projection = state.graphProjection;
    if (!projection) return;
    const depth = Number(projectionDepthSelect.value);
    try {
      const result = projectionDefinition(projection.type).generate(depth, projection.options);
      projection.depth = depth;
      projection.graph = normalizedProjectionGraph(result.graph);
      projection.history = [];
      projection.activeAnchor = projection.options.anchorId || state.selected;
      projection.savedLayout = null;
      depthSelect.value = String(depth);
      state.selected = projection.activeAnchor;
      state.positions = {};
      state.currentLayout = null;
      releaseGraphLayout();
      renderProjectionBar();
      syncTreeSelection();
      updateGraphCount();
      updateTools();
      render();
      fitGraphToView();
      document.querySelector("#graph-command-status").textContent = `${projection.label} regenerated at depth ${depth}.`;
      dispatchEvent(new CustomEvent("graph-selection-changed"));
    } catch (error) {
      projectionDepthSelect.value = String(projection.depth);
      document.querySelector("#graph-command-status").textContent = error.message || "Could not change projection depth.";
    }
  }

  function mergeProjectionGraphs(current, addition) {
    const mergedNodes = new Map(current.nodes.map((node) => [node.id, node]));
    const mergedEdges = new Map(current.edges.map((edge) => [edge.id, edge]));
    normalizedProjectionGraph(addition).nodes.forEach((node) => mergedNodes.set(node.id, node));
    normalizedProjectionGraph(addition).edges.forEach((edge) => mergedEdges.set(edge.id, edge));
    return { nodes: [...mergedNodes.values()], edges: [...mergedEdges.values()] };
  }

  function expandProjection(anchorId = state.selected) {
    const projection = state.graphProjection;
    if (!projection || !anchorId) return;
    try {
      const addition = expansionGraph(projection, anchorId);
      const merged = mergeProjectionGraphs(projection.graph, addition);
      if (merged.nodes.length === projection.graph.nodes.length && merged.edges.length === projection.graph.edges.length) {
        document.querySelector("#graph-command-status").textContent = "This node has no additional elements for the active projection.";
        return;
      }
      projection.history.push({
        graph: structuredClone(projection.graph),
        currentLayout: structuredClone(state.currentLayout),
        graphZoom: state.graphZoom,
        scrollLeft: graphViewport.scrollLeft,
        scrollTop: graphViewport.scrollTop,
        selected: projection.activeAnchor,
      });
      projection.graph = merged;
      projection.activeAnchor = anchorId;
      projection.savedLayout = null;
      state.positions = {};
      state.currentLayout = null;
      releaseGraphLayout();
      renderProjectionBar();
      updateGraphCount();
      updateTools();
      render();
      fitGraphToView();
      document.querySelector("#graph-command-status").textContent = `${graphNode(anchorId)?.label || "Node"} expanded in ${projection.label}.`;
    } catch (error) {
      document.querySelector("#graph-command-status").textContent = error.message || "This node cannot be expanded in the active projection.";
    }
  }

  function restoreProjection() {
    const projection = state.graphProjection;
    if (!projection) return;
    const previous = projection.returnView;
    state.graphProjection = null;
    state.view = previous.view;
    state.positions = previous.positions;
    state.currentLayout = previous.currentLayout;
    state.viewStates = previous.viewStates;
    state.graphZoom = previous.graphZoom;
    state.selected = previous.selected;
    state.selectedRelation = previous.selectedRelation;
    state.layoutLocked = previous.layoutLocked;
    state.layoutSnapshot = previous.layoutSnapshot;
    document.querySelectorAll("[data-graph-view]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.graphView === state.view)));
    const viewLabel = state.view === "structure" ? "Hierarchy" : `${state.view[0].toUpperCase()}${state.view.slice(1)}`;
    document.querySelector("#graph-view-label").textContent = `${viewLabel} Graph`;
    updateLayoutLockControl();
    renderProjectionBar();
    syncTreeSelection();
    updateGraphCount();
    updateTools();
    render();
    requestAnimationFrame(() => {
      applyGraphScale();
      graphViewport.scrollTo({ left: previous.scrollLeft, top: previous.scrollTop });
    });
    document.querySelector("#graph-command-status").textContent = "Interactive projection closed. Previous view restored.";
    dispatchEvent(new CustomEvent("graph-selection-changed"));
  }

  function backProjection() {
    const projection = state.graphProjection;
    if (!projection) return;
    if (!projection.history.length) {
      restoreProjection();
      return;
    }
    const previous = projection.history.pop();
    projection.graph = previous.graph;
    projection.activeAnchor = previous.selected;
    projection.savedLayout = previous.currentLayout;
    state.currentLayout = previous.currentLayout;
    state.graphZoom = previous.graphZoom;
    state.selected = previous.selected;
    renderProjectionBar();
    syncTreeSelection();
    updateGraphCount();
    updateTools();
    render();
    requestAnimationFrame(() => {
      applyGraphScale();
      graphViewport.scrollTo({ left: previous.scrollLeft, top: previous.scrollTop });
    });
    document.querySelector("#graph-command-status").textContent = "Returned to the previous projection step.";
    dispatchEvent(new CustomEvent("graph-selection-changed"));
  }

  function projectSelection() {
    if (state.graphProjection) {
      expandProjection(state.selected);
      return;
    }
    try {
      pendingProjection = recommendedProjection();
      document.querySelector("#projection-kind").textContent = pendingProjection.label;
      projectionCreateDepthSelect.value = depthSelect.value;
      if (!projectionDialog.open) projectionDialog.showModal();
      validateProjectionChoice();
      projectionCreateDepthSelect.focus();
    } catch (error) {
      document.querySelector("#graph-command-status").textContent = error.message || "Could not create the interactive projection.";
    }
  }

  function validateProjectionChoice() {
    if (!pendingProjection) return;
    const depth = Number(projectionCreateDepthSelect.value);
    try {
      const result = projectionDefinition(pendingProjection.type).generate(depth, pendingProjection.options);
      projectionCreateStatus.textContent = `${result.graph.nodes.length} nodes at depth ${depth}.`;
      projectionCreateStatus.classList.remove("invalid");
      projectionCreateButton.disabled = false;
    } catch (error) {
      projectionCreateStatus.textContent = error.message || "This projection cannot be created at the selected depth.";
      projectionCreateStatus.classList.add("invalid");
      projectionCreateButton.disabled = true;
    }
  }

  function closeProjectionDialog() {
    pendingProjection = null;
    projectionDialog.close();
  }

  function confirmProjection(event) {
    event.preventDefault();
    if (!pendingProjection || projectionCreateButton.disabled) return;
    depthSelect.value = projectionCreateDepthSelect.value;
    projectionDepthSelect.value = projectionCreateDepthSelect.value;
    const recommendation = pendingProjection;
    closeProjectionDialog();
    try {
      activateProjection(recommendation);
    } catch (error) {
      document.querySelector("#graph-command-status").textContent = error.message || "Could not create the interactive projection.";
    }
  }

  const definitions = [
    { id: "hierarchy", label: "Package and module hierarchy", deterministic: true, generate: hierarchyDiagram },
    { id: "classes", label: "Class diagram", deterministic: true, generate: classDiagram },
    { id: "calls", label: "Call graph", deterministic: true, generate: callDiagram },
    { id: "modules", label: "Module dependencies", deterministic: true, generate: moduleDiagram },
    { id: "neighborhood", label: "Selection neighborhood", deterministic: true, generate: neighborhoodDiagram },
    { id: "path", label: "Path between pinned nodes", deterministic: true, generate: pathDiagram },
    { id: "sequence", label: "Business sequence (INFERRED)", deterministic: false, generate: inferredSequence },
  ];

  function definition() {
    return definitions.find((item) => item.id === typeSelect.value) || definitions[0];
  }

  function populateTypes() {
    if (typeSelect.options.length) return;
    definitions.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = item.label;
      typeSelect.append(option);
    });
  }

  function populatePins() {
    const byId = nodeMap();
    const pins = [...exploreState.pinnedNodeIds].map((id) => byId.get(id)).filter(Boolean);
    [fromSelect, toSelect].forEach((select) => {
      const previous = select.value;
      select.replaceChildren();
      pins.forEach((node) => {
        const option = document.createElement("option");
        option.value = node.id;
        option.textContent = `${node.kind} / ${node.label}`;
        select.append(option);
      });
      if (pins.some((node) => node.id === previous)) select.value = previous;
    });
    if (pins.length > 1 && fromSelect.value === toSelect.value) toSelect.value = pins[1].id;
  }

  function updateControls() {
    const item = definition();
    pathControls.hidden = item.id !== "path";
    confidence.textContent = item.deterministic ? "DETERMINISTIC" : "INFERRED";
    confidence.className = item.deterministic ? "deterministic" : "inferred";
    generateButton.textContent = item.deterministic ? "Generate" : "Ask Explore";
  }

  async function generate() {
    const item = definition();
    const depth = Number(depthSelect.value);
    status.textContent = item.deterministic ? "Generating from graph" : "Asking configured provider";
    generateButton.disabled = true;
    sourceField.value = "";
    preview.textContent = "";
    preview.classList.remove("diagram-error");
    try {
      const result = await item.generate(depth);
      document.querySelector("#diagram-title").textContent = result.title;
      sourceField.value = result.source;
      document.querySelector("#diagram-copy").disabled = !result.source;
      const markdown = result.markdown || `**DETERMINISTIC** — generated only from current graph nodes and relationships.\n\n${result.summary}\n\n\`\`\`mermaid\n${result.source}\n\`\`\``;
      await globalThis.RichContentRenderer.render(preview, markdown, { prefix: `diagram-${item.id}` });
      status.textContent = result.summary;
    } catch (error) {
      preview.textContent = error.message || "Could not generate this diagram.";
      preview.classList.add("diagram-error");
      status.textContent = error.message || "Generation failed";
      document.querySelector("#diagram-copy").disabled = true;
    } finally {
      generateButton.disabled = false;
    }
  }

  function open() {
    populateTypes();
    populatePins();
    if (state.selected) typeSelect.value = "neighborhood";
    else if (exploreState.pinnedNodeIds.size >= 2) typeSelect.value = "path";
    else typeSelect.value = "hierarchy";
    updateControls();
    if (!dialog.open) dialog.showModal();
    generate();
  }

  document.querySelector("#diagram-close").addEventListener("click", () => dialog.close());
  document.querySelector("#projection-close").addEventListener("click", closeProjectionDialog);
  document.querySelector("#projection-cancel").addEventListener("click", closeProjectionDialog);
  projectionCreateDepthSelect.addEventListener("change", validateProjectionChoice);
  projectionForm.addEventListener("submit", confirmProjection);
  typeSelect.addEventListener("change", () => { updateControls(); generate(); });
  depthSelect.addEventListener("change", () => {
    projectionDepthSelect.value = depthSelect.value;
    generate();
  });
  fromSelect.addEventListener("change", generate);
  toSelect.addEventListener("change", generate);
  generateButton.addEventListener("click", generate);
  document.querySelector("#diagram-copy").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(sourceField.value);
      status.textContent = "Mermaid copied to the clipboard.";
    } catch (error) {
      sourceField.select();
      status.textContent = "Clipboard access was denied. Mermaid source selected for manual copy.";
    }
  });
  document.querySelector("#graph-projection-back").addEventListener("click", backProjection);
  document.querySelector("#graph-projection-restore").addEventListener("click", restoreProjection);
  projectionDepthSelect.addEventListener("change", setProjectionDepth);

  globalThis.HeroDiagrams = Object.freeze({ open, generate, definitions, projectSelection, expandProjection, backProjection, restoreProjection });
})();
