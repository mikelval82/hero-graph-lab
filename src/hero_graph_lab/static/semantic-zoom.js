((globalScope) => {
  const LEVELS = Object.freeze({ native: null, areas: 0, modules: 1, types: 2, members: 3 });
  const KIND_RANK = Object.freeze({ package: 0, module: 1, file: 1, class: 2, function: 3, method: 3 });

  class SemanticZoomProjector {
    project(graph, options = {}) {
      const level = normalizeLevel(options.level);
      if (level === "native") return nativeProjection(graph, options.selectedId);
      const view = normalizeView(options.view);
      const nodeById = new Map((graph?.nodes || []).map((node) => [node.id, node]));
      const scopeId = options.scopeId || graph?.root || null;
      const hiddenNodeIds = new Set(options.hiddenNodeIds || []);
      const maximumRank = LEVELS[level];

      const withinScope = (nodeId) => {
        if (!scopeId) return nodeById.has(nodeId);
        let current = nodeById.get(nodeId);
        while (current?.parent) {
          if (current.parent === scopeId) return true;
          current = nodeById.get(current.parent);
        }
        return false;
      };
      const hiddenByAncestor = (nodeId) => {
        let current = nodeById.get(nodeId);
        while (current && current.id !== scopeId) {
          if (hiddenNodeIds.has(current.id)) return true;
          current = nodeById.get(current.parent);
        }
        return false;
      };
      const retained = (node) => Boolean(
        node
        && node.id !== scopeId
        && node.id !== graph?.root
        && !hiddenByAncestor(node.id)
        && nodeRank(node) <= maximumRank
      );
      const representative = (nodeId) => {
        let current = nodeById.get(nodeId);
        while (current) {
          if (retained(current)) return current;
          if (current.id === scopeId || current.id === graph?.root) return null;
          current = nodeById.get(current.parent);
        }
        return null;
      };

      const projectedNodes = new Map(
        (graph?.nodes || [])
          .filter((node) => withinScope(node.id) && retained(node))
          .map((node) => [node.id, cloneValue(node)]),
      );
      const containmentById = new Map();
      (graph?.edges || [])
        .filter((edge) => (
          edge.kind === "contains"
          && projectedNodes.has(edge.source)
          && projectedNodes.has(edge.target)
        ))
        .forEach((edge) => {
          const edgeId = edgeIdentity(edge);
          if (containmentById.has(edgeId)) return;
          containmentById.set(edgeId, {
            ...cloneValue(edge),
            id: edgeId,
            aggregate: false,
            memberIds: [...(edge.memberIds || [edgeId])].filter(Boolean).sort(),
          });
        });
      const containmentEdges = [...containmentById.values()];

      const relationGroups = new Map();
      (graph?.edges || []).forEach((edge) => {
        if (edge.kind === "contains") return;
        const edgeId = edgeIdentity(edge);
        const sourceInside = withinScope(edge.source);
        const targetInside = withinScope(edge.target);
        if (!sourceInside && !targetInside) return;
        const source = representative(edge.source);
        const target = representative(edge.target);
        if (!source || !target || source.id === target.id) return;
        if (!projectedNodes.has(source.id)) projectedNodes.set(source.id, { ...cloneValue(source), context: true });
        if (!projectedNodes.has(target.id)) projectedNodes.set(target.id, { ...cloneValue(target), context: true });
        const status = edge.status || "observed";
        const label = edge.label || "";
        const properties = stableValue(edge.properties || {});
        const key = stableStringify([source.id, target.id, edge.kind, status, label, properties]);
        const group = relationGroups.get(key) || {
          source: source.id,
          target: target.id,
          kind: edge.kind,
          status,
          label,
          properties,
          memberIds: [],
          originalIds: [],
          mapped: false,
        };
        group.memberIds.push(...(edge.memberIds || [edgeId]).filter(Boolean));
        group.originalIds.push(edgeId);
        group.mapped ||= source.id !== edge.source || target.id !== edge.target;
        relationGroups.set(key, group);
      });

      const relationEdges = [...relationGroups.entries()]
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([, group], index) => {
          const memberIds = [...new Set(group.memberIds)].sort();
          const aggregate = group.mapped || memberIds.length > 1 || group.originalIds.length > 1;
          return {
            id: aggregate
              ? `semantic:${level}:${index}:${group.source}:${group.kind}:${group.target}`
              : group.originalIds[0],
            source: group.source,
            target: group.target,
            kind: group.kind,
            status: group.status,
            label: group.label || (memberIds.length > 1 ? `${memberIds.length} ${group.kind}` : group.kind),
            properties: cloneValue(group.properties),
            memberIds,
            count: memberIds.length,
            editLabel: group.label || group.kind,
            aggregate,
          };
        });

      const selectedId = options.selectedId ? representative(options.selectedId)?.id || null : null;
      const flow = {
        root: scopeId,
        source: graph?.source,
        nodes: [...projectedNodes.values()].sort((left, right) => left.id.localeCompare(right.id)),
        edges: [...containmentEdges, ...relationEdges].sort((left, right) => left.id.localeCompare(right.id)),
        selectedId,
        semanticLevel: level,
        semanticSelectionId: selectedId,
      };
      if (view === "structure") {
        return { ...flow, edges: flow.edges.filter((edge) => edge.kind === "contains") };
      }
      if (view === "focus" && selectedId && projectedNodes.has(selectedId)) {
        const edges = flow.edges.filter((edge) => (
          edge.kind === "calls" && (edge.source === selectedId || edge.target === selectedId)
        ));
        const nodeIds = new Set([selectedId]);
        edges.forEach((edge) => {
          nodeIds.add(edge.source);
          nodeIds.add(edge.target);
        });
        return {
          ...flow,
          nodes: flow.nodes.filter((node) => nodeIds.has(node.id)),
          edges,
        };
      }
      return flow;
    }
  }

  function semanticDetail(zoom) {
    const value = Number.isFinite(Number(zoom)) ? Number(zoom) : 1;
    if (value < 0.45) return "overview";
    if (value < 0.9) return "context";
    return "detail";
  }

  function transitionSelection({
    currentLevel,
    nextLevel,
    selectedId,
    rememberedSelection,
    mapSelection,
  }) {
    const current = normalizeLevel(currentLevel);
    const next = normalizeLevel(nextLevel);
    if (current === next) return { selectedId, rememberedSelection };
    const pending = rememberedSelection
      && selectedId === rememberedSelection.mappedId
      ? rememberedSelection
      : null;
    const sourceId = pending?.sourceId || selectedId || null;
    if (next === "native") {
      return {
        selectedId: pending?.sourceId || selectedId || null,
        rememberedSelection: null,
      };
    }
    const mappedId = sourceId ? mapSelection(sourceId, next) : null;
    if (!sourceId || mappedId === sourceId) {
      return { selectedId: mappedId || sourceId, rememberedSelection: null };
    }
    return {
      selectedId: mappedId,
      rememberedSelection: { sourceId, mappedId },
    };
  }

  function nativeProjection(graph, selectedId) {
    const nodes = (graph?.nodes || []).map(cloneValue);
    const nodeIds = new Set(nodes.map((node) => node.id));
    return {
      ...cloneValue(graph || {}),
      nodes,
      edges: (graph?.edges || []).map(cloneValue),
      selectedId: nodeIds.has(selectedId) ? selectedId : null,
      semanticLevel: "native",
      semanticSelectionId: nodeIds.has(selectedId) ? selectedId : null,
    };
  }

  function normalizeLevel(level) {
    const value = String(level || "native");
    if (!Object.hasOwn(LEVELS, value)) throw new Error(`Unknown architectural level: ${value}`);
    return value;
  }

  function normalizeView(view) {
    const value = String(view || "flow");
    if (!["flow", "structure", "focus"].includes(value)) throw new Error(`Unknown graph view: ${value}`);
    return value;
  }

  function nodeRank(node) {
    return KIND_RANK[node?.kind] ?? LEVELS.members;
  }

  function stableStringify(value) {
    return JSON.stringify(stableValue(value));
  }

  function edgeIdentity(edge) {
    if (edge?.id) return edge.id;
    const signature = stableStringify({
      source: edge?.source || "",
      target: edge?.target || "",
      kind: edge?.kind || "custom",
      status: edge?.status || "observed",
      label: edge?.label || "",
      properties: edge?.properties || {},
    });
    let hash = 14695981039346656037n;
    for (let index = 0; index < signature.length; index += 1) {
      hash ^= BigInt(signature.charCodeAt(index));
      hash = BigInt.asUintN(64, hash * 1099511628211n);
    }
    return `observed:${hash.toString(16).padStart(16, "0")}`;
  }

  function stableValue(value) {
    if (Array.isArray(value)) return value.map(stableValue);
    if (value && typeof value === "object") {
      return Object.fromEntries(
        Object.entries(value)
          .sort(([left], [right]) => left.localeCompare(right))
          .map(([key, item]) => [key, stableValue(item)]),
      );
    }
    return value;
  }

  function cloneValue(value) {
    if (value === undefined) return undefined;
    return globalScope.structuredClone
      ? globalScope.structuredClone(value)
      : JSON.parse(JSON.stringify(value));
  }

  const api = Object.freeze({
    LEVELS,
    SemanticZoomProjector,
    semanticDetail,
    transitionSelection,
  });
  globalScope.HeroSemanticZoom = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis === "undefined" ? this : globalThis);
