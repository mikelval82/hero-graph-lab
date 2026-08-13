function svgElement(tag, attributes = {}) {
  const element = document.createElementNS(SVG_NS, tag);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
  return element;
}

function graphWidth() {
  return matchMedia("(max-width: 680px)").matches ? 600 : 1000;
}

function graphTextScale() {
  const size = Number.parseFloat(getComputedStyle(document.querySelector("#graph-panel")).getPropertyValue("--panel-font-size"));
  return clamp((Number.isFinite(size) ? size : 14) / 14, .75, 1.6);
}

function graphFontSize() {
  return 14 * graphTextScale();
}

function graphTextWidth(text, size, weight = 400, familyVariable = "--mono") {
  const context = graphTextWidth.context || (graphTextWidth.context = document.createElement("canvas").getContext("2d"));
  const family = getComputedStyle(document.documentElement).getPropertyValue(familyVariable).trim();
  context.font = `${weight} ${size}px ${family}`;
  return context.measureText(text).width;
}

function nodeDisplayLabel(node) {
  return node.label.length > 20 ? `${node.label.slice(0, 18)}...` : node.label;
}

function nodeStatusText(node) {
  const childCount = scopeChildren(node.id).length;
  if (node.context) return "CONTEXT";
  if (childCount) return `OPEN / ${childCount}`;
  return { observed: "CODE", proposed: "NEW", modified: "EDIT", removed: "DELETE" }[node.status || "observed"];
}

function graphNodeMetrics(node) {
  const scale = graphTextScale();
  const fontSize = graphFontSize();
  const baseWidth = node.kind === "package" ? 180 : node.kind === "module" ? 170 : node.kind === "class" ? 150 : 138;
  const baseHeight = node.kind === "package" || node.kind === "module" ? 76 : 62;
  const labelWidth = graphTextWidth(nodeDisplayLabel(node), fontSize, 500, "--sans");
  const metadataSize = Math.max(11, fontSize - 2);
  const statusSize = Math.max(9, fontSize - 4);
  const contentWidth = Math.max(
    labelWidth,
    graphTextWidth(node.kind, metadataSize),
    graphTextWidth(nodeStatusText(node), statusSize),
  );
  return { width: Math.ceil(Math.max(baseWidth * scale, contentWidth + 28 * scale)), height: Math.round(baseHeight * scale), scale };
}

function graphLayoutMetrics(nodes) {
  const metrics = nodes.map(graphNodeMetrics);
  const maxWidth = Math.max(...metrics.map(({ width }) => width), 0);
  return {
    maxWidth,
    columnGap: Math.max(210 * graphTextScale(), maxWidth + 40 * graphTextScale()),
    rowGap: Math.max(100 * graphTextScale(), Math.max(...metrics.map(({ height }) => height), 0) + 24 * graphTextScale()),
  };
}

function updateGraphViewport(width = state.graphWidth, height = state.graphHeight) {
  state.graphWidth = width;
  state.graphHeight = height;
  graphElement.setAttribute("viewBox", `0 0 ${width} ${height}`);
}

function stronglyConnectedComponents(nodeIds, edges) {
  const outgoing = new Map(nodeIds.map((nodeId) => [nodeId, []]));
  edges.forEach((edge) => outgoing.get(edge.source)?.push(edge.target));
  const indexByNode = new Map();
  const lowLink = new Map();
  const stack = [];
  const onStack = new Set();
  const components = [];
  let nextIndex = 0;

  const visit = (nodeId) => {
    indexByNode.set(nodeId, nextIndex);
    lowLink.set(nodeId, nextIndex);
    nextIndex += 1;
    stack.push(nodeId);
    onStack.add(nodeId);
    outgoing.get(nodeId).forEach((targetId) => {
      if (!indexByNode.has(targetId)) {
        visit(targetId);
        lowLink.set(nodeId, Math.min(lowLink.get(nodeId), lowLink.get(targetId)));
      } else if (onStack.has(targetId)) {
        lowLink.set(nodeId, Math.min(lowLink.get(nodeId), indexByNode.get(targetId)));
      }
    });
    if (lowLink.get(nodeId) !== indexByNode.get(nodeId)) return;
    const component = [];
    let member;
    do {
      member = stack.pop();
      onStack.delete(member);
      component.push(member);
    } while (member !== nodeId);
    components.push(component);
  };

  nodeIds.forEach((nodeId) => { if (!indexByNode.has(nodeId)) visit(nodeId); });
  return components;
}

function connectivityLevels(nodes, edges) {
  const nodeIds = nodes.map((node) => node.id);
  const components = stronglyConnectedComponents(nodeIds, edges);
  const componentByNode = new Map();
  components.forEach((component, index) => component.forEach((nodeId) => componentByNode.set(nodeId, index)));
  const outgoing = new Map(components.map((_, index) => [index, new Set()]));
  const incoming = new Map(components.map((_, index) => [index, 0]));
  edges.forEach((edge) => {
    const source = componentByNode.get(edge.source);
    const target = componentByNode.get(edge.target);
    if (source === undefined || target === undefined || source === target || outgoing.get(source).has(target)) return;
    outgoing.get(source).add(target);
    incoming.set(target, incoming.get(target) + 1);
  });
  const componentLevels = new Map(components.map((_, index) => [index, 0]));
  const queue = [...incoming.entries()].filter(([, count]) => count === 0).map(([index]) => index);
  for (const component of queue) {
    outgoing.get(component).forEach((target) => {
      componentLevels.set(target, Math.max(componentLevels.get(target), componentLevels.get(component) + 1));
      incoming.set(target, incoming.get(target) - 1);
      if (incoming.get(target) === 0) queue.push(target);
    });
  }
  return new Map(nodeIds.map((nodeId) => [nodeId, componentLevels.get(componentByNode.get(nodeId))]));
}

function orderColumns(columns, edges) {
  const neighbors = new Map([...columns.values()].flat().map((node) => [node.id, new Set()]));
  edges.forEach((edge) => {
    neighbors.get(edge.source)?.add(edge.target);
    neighbors.get(edge.target)?.add(edge.source);
  });
  [...columns.values()].forEach((column) => column.sort((left, right) => left.label.localeCompare(right.label)));
  for (let pass = 0; pass < 4; pass += 1) {
    const order = new Map();
    [...columns.values()].forEach((column) => column.forEach((node, index) => order.set(node.id, index)));
    [...columns.keys()].sort((left, right) => pass % 2 ? right - left : left - right).forEach((level) => {
      columns.get(level).sort((left, right) => {
        const barycenter = (node) => {
          const connected = [...neighbors.get(node.id)].filter((nodeId) => order.has(nodeId));
          return connected.length ? connected.reduce((sum, nodeId) => sum + order.get(nodeId), 0) / connected.length : order.get(node.id);
        };
        return barycenter(left) - barycenter(right) || left.label.localeCompare(right.label);
      });
    });
  }
}

function flowLayout(nodes, edges) {
  const scale = graphTextScale();
  const { columnGap, rowGap } = graphLayoutMetrics(nodes);
  const graphEdges = edges.filter((edge) => edge.status !== "removed");
  const levels = connectivityLevels(nodes, graphEdges);
  const structuralEdges = graphEdges.filter((edge) => edge.kind === "contains");
  for (let pass = 0; pass < nodes.length; pass += 1) {
    let changed = false;
    structuralEdges.forEach((edge) => {
      const targetLevel = Math.max(levels.get(edge.target), levels.get(edge.source) + 1);
      if (targetLevel === levels.get(edge.target)) return;
      levels.set(edge.target, targetLevel);
      changed = true;
    });
    if (!changed) break;
  }
  const usedLevels = [...new Set(levels.values())].sort((left, right) => left - right);
  const normalizedLevel = new Map(usedLevels.map((level, index) => [level, index]));
  const columns = new Map();
  nodes.forEach((node) => {
    const level = normalizedLevel.get(levels.get(node.id));
    if (!columns.has(level)) columns.set(level, []);
    columns.get(level).push(node);
  });
  orderColumns(columns, graphEdges);
  const maxLevel = Math.max(...columns.keys(), 0);
  const maxColumnLength = Math.max(...[...columns.values()].map((column) => column.length), 1);
  const horizontalMargin = 100 * scale;
  const verticalMargin = 125 * scale;
  const width = Math.max(graphWidth(), horizontalMargin * 2 + maxLevel * columnGap);
  const height = Math.max(680, verticalMargin * 2 + (maxColumnLength - 1) * rowGap);
  const positions = {};
  columns.forEach((column, level) => column.forEach((node, index) => {
    const x = maxLevel === 0 ? width / 2 : horizontalMargin + level * ((width - horizontalMargin * 2) / maxLevel);
    const y = column.length === 1 ? height / 2 : verticalMargin + index * ((height - verticalMargin * 2) / (column.length - 1));
    positions[node.id] = { x, y };
  }));
  return { width, height, positions };
}

function structureLayout(nodes, edges) {
  const scale = graphTextScale();
  const { columnGap, rowGap: contentRowGap } = graphLayoutMetrics(nodes);
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const children = new Map(nodes.map((node) => [node.id, []]));
  const childIds = new Set();
  edges.filter((edge) => edge.kind === "contains" && edge.status !== "removed").forEach((edge) => {
    if (!nodeById.has(edge.source) || !nodeById.has(edge.target)) return;
    children.get(edge.source).push(edge.target);
    childIds.add(edge.target);
  });
  children.forEach((nodeIds) => nodeIds.sort((left, right) => nodeById.get(left).label.localeCompare(nodeById.get(right).label)));
  const roots = nodes.filter((node) => !childIds.has(node.id)).sort((left, right) => left.label.localeCompare(right.label));
  const positions = {};
  const visited = new Set();
  const visiting = new Set();
  const rowGap = Math.max(112 * scale, contentRowGap);
  const levelGap = Math.max(220 * scale, columnGap);
  const topMargin = 70 * scale;
  let nextRow = 0;
  let maxDepth = 0;

  const place = (nodeId, depth) => {
    if (visited.has(nodeId)) return positions[nodeId].y;
    if (visiting.has(nodeId)) {
      const y = topMargin + nextRow * rowGap;
      nextRow += 1;
      return y;
    }
    visiting.add(nodeId);
    maxDepth = Math.max(maxDepth, depth);
    const visibleChildren = children.get(nodeId).filter((childId) => !visiting.has(childId));
    let y;
    if (visibleChildren.length) {
      const childRows = visibleChildren.map((childId) => place(childId, depth + 1));
      y = (childRows[0] + childRows[childRows.length - 1]) / 2;
    } else {
      y = topMargin + nextRow * rowGap;
      nextRow += 1;
    }
    visiting.delete(nodeId);
    visited.add(nodeId);
    positions[nodeId] = { x: 110 * scale + depth * levelGap, y };
    return y;
  };

  roots.forEach((node) => place(node.id, 0));
  nodes.filter((node) => !visited.has(node.id)).sort((left, right) => left.label.localeCompare(right.label)).forEach((node) => place(node.id, 0));
  const width = Math.max(graphWidth(), 220 * scale + maxDepth * levelGap);
  const height = Math.max(680, topMargin * 2 + Math.max(nextRow - 1, 0) * rowGap);
  return { width, height, positions };
}

function focusLayout(nodes, edges) {
  const scale = graphTextScale();
  const { maxWidth, columnGap, rowGap } = graphLayoutMetrics(nodes);
  const selected = nodes.find((node) => node.id === state.selected);
  if (!selected) return flowLayout(nodes, edges);
  const outgoingIds = new Set(edges.filter((edge) => edge.source === selected.id).map((edge) => edge.target));
  const incomingIds = new Set(edges.filter((edge) => edge.target === selected.id && !outgoingIds.has(edge.source)).map((edge) => edge.source));
  const width = Math.max(graphWidth(), 2 * columnGap + maxWidth);
  const height = Math.max(680, 180 * scale + Math.max(incomingIds.size, outgoingIds.size, 1) * rowGap);
  const positions = { [selected.id]: { x: width / 2, y: height / 2 } };
  const placeColumn = (nodeIds, x) => {
    const ids = [...nodeIds];
    ids.forEach((nodeId, index) => {
      positions[nodeId] = { x, y: height * (index + 1) / (ids.length + 1) };
    });
  };
  placeColumn(incomingIds, width / 2 - columnGap);
  placeColumn(outgoingIds, width / 2 + columnGap);
  return { width, height, positions };
}

function curve(source, target) {
  const midpoint = (source.x + target.x) / 2;
  return `M ${source.x} ${source.y} C ${midpoint} ${source.y}, ${midpoint} ${target.y}, ${target.x} ${target.y}`;
}

function currentPositions(graph) {
  if (state.layoutLocked && state.layoutSnapshot) {
    updateGraphViewport(state.layoutSnapshot.width, state.layoutSnapshot.height);
    applyGraphScale();
    state.currentLayout = {
      projectionKey: graphProjectionKey(graph),
      positions: structuredClone(state.layoutSnapshot.positions),
      width: state.layoutSnapshot.width,
      height: state.layoutSnapshot.height,
    };
    return state.layoutSnapshot.positions;
  }
  const projectionKey = graphProjectionKey(graph);
  const savedLayout = state.graphProjection?.savedLayout || state.viewStates[state.view]?.layout;
  if (savedLayout?.projectionKey === projectionKey) {
    updateGraphViewport(savedLayout.width, savedLayout.height);
    applyGraphScale();
    state.currentLayout = structuredClone(savedLayout);
    return structuredClone(savedLayout.positions);
  }
  const layout = state.view === "structure"
    ? structureLayout(graph.nodes, graph.edges)
    : state.view === "focus"
      ? focusLayout(graph.nodes, graph.edges)
      : flowLayout(graph.nodes, graph.edges);
  updateGraphViewport(layout.width, layout.height);
  applyGraphScale();
  const positions = layout.positions;
  if (state.view === "flow") Object.assign(positions, state.positions);
  state.currentLayout = {
    projectionKey,
    positions: structuredClone(positions),
    width: layout.width,
    height: layout.height,
  };
  return positions;
}

function relationLabelOffsets(edges) {
  const groups = new Map();
  edges.forEach((edge) => {
    const key = [edge.source, edge.target].sort().join("|");
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(edge);
  });
  const offsets = new Map();
  const spacing = 24 * graphTextScale();
  groups.forEach((group) => group.sort((left, right) => left.id.localeCompare(right.id)).forEach((edge, index) => {
    offsets.set(edge.id, (index - (group.length - 1) / 2) * spacing);
  }));
  return offsets;
}

function relationMidpoint(source, target, offset = 0) {
  return { x: (source.x + target.x) / 2, y: (source.y + target.y) / 2 + offset };
}

function relationText(edge) {
  return edge.label || edge.kind.replaceAll("_", " ");
}

function relationDetails(edge) {
  const properties = Object.entries(edge.properties || {}).map(([key, value]) => `${key}=${value}`);
  return [relationText(edge), ...properties].join("\n");
}

function relatedNodeIds(graph) {
  const related = new Set([state.selected]);
  if (state.selected) graph.edges.forEach((edge) => {
    if (edge.source === state.selected) related.add(edge.target);
    if (edge.target === state.selected) related.add(edge.source);
  });
  return related;
}

function selectionDimmingActive() {
  return Boolean(state.selected && !state.graphProjection && state.view !== "structure");
}

function updateGraphSelectionStyles(graph = navigationGraph()) {
  const related = relatedNodeIds(graph);
  const dimSelection = selectionDimmingActive();
  nodeLayer.querySelectorAll(".graph-node").forEach((node) => {
    const nodeId = node.dataset.nodeId;
    node.classList.toggle("selected", state.selected === nodeId);
    node.classList.toggle("dimmed", dimSelection && !related.has(nodeId));
  });
  const edgeById = new Map(graph.edges.map((edge) => [edge.id, edge]));
  graphElement.querySelectorAll("[data-edge-id]").forEach((element) => {
    const edge = edgeById.get(element.dataset.edgeId);
    const dimmed = Boolean(dimSelection && edge && !(related.has(edge.source) && related.has(edge.target)));
    element.classList.toggle("dimmed", dimmed);
    element.classList.remove("selected", "relation-dimmed");
  });
}

function render() {
  if (!state.graph) return;
  edgeLayer.replaceChildren(); edgeLabelLayer.replaceChildren(); nodeLayer.replaceChildren();
  const visibleGraph = navigationGraph();
  const positions = currentPositions(visibleGraph);
  const related = relatedNodeIds(visibleGraph);
  const dimSelection = selectionDimmingActive();
  const edgeLabelOffsets = relationLabelOffsets(visibleGraph.edges);

  visibleGraph.edges.forEach((edge) => {
    const source = positions[edge.source]; const target = positions[edge.target];
    if (!source || !target) return;
    const pathData = curve(source, target);
    const relationSelected = state.selectedRelation === edge.id;
    const traceDimmed = state.callTrace && !edge.memberIds.some((edgeId) => state.callTrace.edgeIds.has(edgeId));
    const nodeDimmed = traceDimmed || (!state.callTrace && dimSelection && !(related.has(edge.source) && related.has(edge.target))) ? " dimmed" : "";
    const relationDimmed = state.selectedRelation && !relationSelected ? " relation-dimmed" : "";
    const dimmed = `${nodeDimmed}${relationDimmed}`;
    const traced = edge.memberIds.some((edgeId) => state.callTrace?.edgeIds.has(edgeId));
    const visiblePath = svgElement("path", { d: pathData, class: `graph-edge ${edge.kind} ${edge.status || "observed"}${traced ? " traced" : ""}${relationSelected ? " selected" : ""}${dimmed}`, "data-edge-id": edge.id });
    const title = svgElement("title"); title.textContent = relationDetails(edge); visiblePath.append(title);
    edgeLayer.append(visiblePath);
    const hitPath = svgElement("path", { d: pathData, class: `edge-hit${dimmed}`, "data-edge-id": edge.id });
    hitPath.addEventListener("click", (event) => { event.stopPropagation(); selectRelation(edge); });
    edgeLayer.append(hitPath);

    if (state.view === "structure") return;

    const midpoint = relationMidpoint(source, target, edgeLabelOffsets.get(edge.id));
    const text = traced ? `${edge.traceDepth} · ${relationText(edge)}` : relationText(edge);
    const textScale = graphTextScale();
    const labelHeight = 20 * textScale;
    const displayedText = text.length > 24 ? `${text.slice(0, 22)}...` : text;
    const width = Math.max(42 * textScale, graphTextWidth(displayedText, Math.max(11, graphFontSize() - 2)) + 16 * textScale);
    const labelAttributes = { class: `edge-label ${edge.status || "observed"}${edge.aggregate ? " aggregate" : ""}${relationSelected ? " selected" : ""}${dimmed}`, transform: `translate(${midpoint.x} ${midpoint.y})`, "aria-label": `relationship ${text}`, tabindex: "0", role: "button", "data-edge-id": edge.id };
    const label = svgElement("g", labelAttributes);
    label.append(svgElement("rect", { x: -width / 2, y: -labelHeight / 2, width, height: labelHeight, rx: 3 }));
    const labelText = svgElement("text", { x: 0, y: 3 * textScale, "text-anchor": "middle" }); labelText.textContent = displayedText;
    label.append(labelText);
    label.addEventListener("click", (event) => { event.stopPropagation(); selectRelation(edge); });
    label.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") selectRelation(edge); });
    edgeLabelLayer.append(label);
  });
  visibleGraph.nodes.forEach((node) => {
    const position = positions[node.id];
    const status = node.status || "observed";
    const traceDepth = state.callTrace?.nodeDepths.get(node.id);
    const traceClass = traceDepth === 0 ? " trace-root" : traceDepth !== undefined ? " traced" : "";
    const traceDimmed = state.callTrace && traceDepth === undefined;
    const group = svgElement("g", { class: `graph-node ${status}${node.context ? " context" : ""}${traceClass}${state.selected === node.id ? " selected" : ""}${traceDimmed || (!state.callTrace && dimSelection && !related.has(node.id)) ? " dimmed" : ""}`, transform: `translate(${position.x} ${position.y})`, tabindex: "0", role: "button", "aria-label": `${status} ${node.kind} ${node.label}`, "data-node-id": node.id });
    const { width, height, scale } = graphNodeMetrics(node);
    group.append(svgElement("rect", { x: -width / 2, y: -height / 2, width, height, rx: 3, class: `node-shape ${node.kind}` }));
    const dark = node.kind === "package" || node.kind === "module" || node.kind === "class";
    const kind = svgElement("text", { x: 0, y: -13 * scale, "text-anchor": "middle", class: `node-kind${dark ? " on-dark" : ""}` }); kind.textContent = node.kind;
    const label = svgElement("text", { x: 0, y: 4 * scale, "text-anchor": "middle", class: `node-label${dark ? " on-dark" : ""}` }); label.textContent = nodeDisplayLabel(node);
    const statusLabel = svgElement("text", { x: 0, y: height / 2 - 7 * scale, "text-anchor": "middle", class: `node-status${dark ? " on-dark" : ""}` });
    statusLabel.textContent = nodeStatusText(node);
    group.append(kind, label, statusLabel);
    if (traceDepth !== undefined) {
      const badge = svgElement("g", { class: "trace-badge", transform: `translate(${-width / 2 + 2 * scale} ${-height / 2 + 2 * scale})`, "aria-label": `Call depth ${traceDepth}` });
      badge.append(svgElement("circle", { r: 12 * scale }));
      const badgeText = svgElement("text", { x: 0, y: 3 * scale, "text-anchor": "middle" }); badgeText.textContent = traceDepth;
      badge.append(badgeText);
      group.append(badge);
    }
    if (status === "removed") group.append(svgElement("line", { x1: -width / 2 + 9 * scale, y1: height / 2 - 8 * scale, x2: width / 2 - 9 * scale, y2: -height / 2 + 8 * scale, class: "removal-mark" }));
    if (status !== "removed" && !node.context && !state.graphProjection) {
      const connectorHalo = svgElement("circle", { cx: width / 2, cy: 0, r: 15 * scale, class: "connector-halo" });
      const connector = svgElement("circle", { cx: width / 2, cy: 0, r: 6 * scale, class: "connector", role: "button", "aria-label": `Connect from ${node.label}` });
      const start = (event) => startConnection(event, node.id, { x: position.x + width / 2, y: position.y });
      connectorHalo.addEventListener("pointerdown", start);
      connector.addEventListener("pointerdown", start);
      group.append(connectorHalo, connector);
    }
    group.addEventListener("pointerdown", (event) => startDrag(event, node.id, position));
    group.addEventListener("click", (event) => event.stopPropagation());
    group.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") toggleSelection(node.id);
    });
    nodeLayer.append(group);
  });
}
