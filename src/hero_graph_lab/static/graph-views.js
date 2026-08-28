((globalScope) => {
  function node(context, nodeId) {
    return context.nodeById.get(nodeId);
  }

  function children(context, parentId) {
    return context.childrenByParent.get(parentId) || [];
  }

  function canEnterScope(context, nodeId) {
    return children(context, nodeId).length > 0 && node(context, nodeId)?.status !== "removed";
  }

  function isDescendant(context, nodeId, ancestorId) {
    let current = node(context, nodeId);
    while (current?.parent) {
      if (current.parent === ancestorId) return true;
      current = node(context, current.parent);
    }
    return false;
  }

  function descendantIds(context, nodeId) {
    const descendants = new Set();
    const pending = [...children(context, nodeId)];
    while (pending.length) {
      const child = pending.pop();
      descendants.add(child.id);
      pending.push(...children(context, child.id));
    }
    return descendants;
  }

  function outgoingCallTrace(graph, rootId, maxDepth = 1) {
    const nodeDepths = new Map([[rootId, 0]]);
    const edgeIds = new Set();
    let frontier = [rootId];
    for (let depth = 1; depth <= maxDepth && frontier.length; depth += 1) {
      const next = [];
      frontier.forEach((sourceId) => {
        graph.edges.forEach((edge) => {
          if (edge.kind !== "calls" || edge.status === "removed" || edge.source !== sourceId) return;
          edgeIds.add(edge.id);
          if (nodeDepths.has(edge.target)) return;
          nodeDepths.set(edge.target, depth);
          next.push(edge.target);
        });
      });
      frontier = next;
    }
    return { rootId, maxDepth, nodeDepths, edgeIds };
  }

  function callTraceGraph(context) {
    const trace = context.callTrace;
    if (!trace) return { nodes: [], edges: [] };
    const nodes = [...trace.nodeDepths].map(([nodeId, traceDepth]) => {
      const graphNode = node(context, nodeId);
      return graphNode ? { ...graphNode, context: false, traceDepth } : null;
    }).filter(Boolean);
    const nodeIds = new Set(nodes.map((graphNode) => graphNode.id));
    const edges = context.graph.edges
      .filter((edge) => trace.edgeIds.has(edge.id) && nodeIds.has(edge.source) && nodeIds.has(edge.target))
      .map((edge) => ({
        ...edge,
        aggregate: false,
        memberIds: [edge.id],
        traced: true,
        traceDepth: trace.nodeDepths.get(edge.target),
      }));
    return { nodes, edges };
  }

  function visibleHierarchyNodes(context, expandedNodes = context.inlineExpanded) {
    const nodes = [];
    const appendChildren = (parentId) => {
      children(context, parentId).forEach((child) => {
        if (context.hiddenGraphNodes.has(child.id)) return;
        nodes.push({ ...child, context: false });
        if (expandedNodes.has(child.id)) appendChildren(child.id);
      });
    };
    appendChildren(context.scope);
    return nodes;
  }

  function visibleRepresentative(context, nodeId, visibleIds) {
    let current = node(context, nodeId);
    while (current && current.id !== context.scope) {
      if (visibleIds.has(current.id)) return current;
      current = node(context, current.parent);
    }
    return null;
  }

  function flowGraph(context, expandedNodes = context.inlineExpanded) {
    const scopeId = context.scope || context.graph.root;
    const scopedContext = { ...context, scope: scopeId };
    const nodes = visibleHierarchyNodes(scopedContext, expandedNodes);
    const nodeIds = new Set(nodes.map((graphNode) => graphNode.id));
    context.callTrace?.nodeDepths.forEach((depth, nodeId) => {
      if (nodeIds.has(nodeId)) return;
      const graphNode = node(context, nodeId);
      if (!graphNode) return;
      nodes.push({ ...graphNode, context: true, traceDepth: depth });
      nodeIds.add(nodeId);
    });
    const groupedEdges = new Map();
    const directEdges = context.graph.edges
      .filter((edge) => edge.kind === "contains" && nodeIds.has(edge.source) && nodeIds.has(edge.target))
      .map((edge) => ({ ...edge, aggregate: false, memberIds: [edge.id] }));

    context.graph.edges.filter((edge) => edge.kind !== "contains").forEach((edge) => {
      const sourceBranch = visibleRepresentative(scopedContext, edge.source, nodeIds);
      const targetBranch = visibleRepresentative(scopedContext, edge.target, nodeIds);
      if (!sourceBranch && !targetBranch) return;
      const sourceInsideScope = edge.source === scopeId || isDescendant(context, edge.source, scopeId);
      const targetInsideScope = edge.target === scopeId || isDescendant(context, edge.target, scopeId);
      const source = sourceBranch || (!sourceInsideScope && !context.hiddenGraphNodes.has(edge.source) ? node(context, edge.source) : null);
      const target = targetBranch || (!targetInsideScope && !context.hiddenGraphNodes.has(edge.target) ? node(context, edge.target) : null);
      if (!source || !target || source.id === target.id) return;
      if (!nodeIds.has(source.id)) {
        nodes.push({ ...source, context: true });
        nodeIds.add(source.id);
      }
      if (!nodeIds.has(target.id)) {
        nodes.push({ ...target, context: true });
        nodeIds.add(target.id);
      }
      if (source.id === edge.source && target.id === edge.target) {
        directEdges.push({
          ...edge,
          aggregate: false,
          memberIds: [edge.id],
          traced: context.callTrace?.edgeIds.has(edge.id),
          traceDepth: context.callTrace?.nodeDepths.get(edge.target),
        });
        return;
      }
      const status = edge.status || "observed";
      const label = edge.label || "";
      const properties = edge.properties || {};
      const propertyKey = JSON.stringify(Object.entries(properties).sort());
      const key = `${source.id}|${target.id}|${edge.kind}|${status}|${label}|${propertyKey}`;
      const grouped = groupedEdges.get(key) || { source: source.id, target: target.id, kind: edge.kind, status, label, properties, count: 0, memberIds: [] };
      grouped.count += 1;
      grouped.memberIds.push(edge.id);
      groupedEdges.set(key, grouped);
    });

    const edges = Array.from(groupedEdges.values()).map((edge) => ({
      id: `aggregate:${scopeId}:${edge.source}:${edge.kind}:${edge.target}:${edge.status}`,
      source: edge.source,
      target: edge.target,
      kind: edge.kind,
      status: edge.status,
      label: edge.label || (edge.count > 1 ? `${edge.count} ${edge.kind}` : edge.kind),
      properties: edge.properties,
      memberIds: edge.memberIds,
      count: edge.count,
      editLabel: edge.label || edge.kind,
      aggregate: true,
    }));
    return { nodes, edges: [...directEdges, ...edges] };
  }

  function structureGraph(context) {
    const nodes = visibleHierarchyNodes(context);
    const nodeIds = new Set(nodes.map((graphNode) => graphNode.id));
    const edges = context.graph.edges
      .filter((edge) => edge.kind === "contains" && nodeIds.has(edge.source) && nodeIds.has(edge.target))
      .map((edge) => ({ ...edge, aggregate: false, memberIds: [edge.id] }));
    return { nodes, edges };
  }

  function focusGraph(context) {
    const expandedNodes = new Set(context.inlineExpanded);
    if (context.selected) expandedNodes.delete(context.selected);
    const graph = flowGraph(context, expandedNodes);
    if (!context.selected || !graph.nodes.some((graphNode) => graphNode.id === context.selected)) return graph;
    const edges = graph.edges.filter((edge) => edge.kind === "calls" && (edge.source === context.selected || edge.target === context.selected));
    const nodeIds = new Set([context.selected]);
    edges.forEach((edge) => {
      nodeIds.add(edge.source);
      nodeIds.add(edge.target);
    });
    return { nodes: graph.nodes.filter((graphNode) => nodeIds.has(graphNode.id)), edges };
  }

  function highlightedGraph(graph, selectedId) {
    if (!selectedId || !graph.nodes.some((graphNode) => graphNode.id === selectedId)) return graph;
    const nodeIds = new Set([selectedId]);
    graph.edges.forEach((edge) => {
      if (edge.source !== selectedId && edge.target !== selectedId) return;
      nodeIds.add(edge.source);
      nodeIds.add(edge.target);
    });
    return {
      nodes: graph.nodes.filter((graphNode) => nodeIds.has(graphNode.id)),
      edges: graph.edges.filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target)),
    };
  }

  function flowActiveNodeId(flowJourney) {
    return flowJourney.at(-1)?.nodeId || null;
  }

  function flowRelationSnapshot(edge) {
    if (!edge) return null;
    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      kind: edge.kind,
      label: edge.label || "",
      status: edge.status || "observed",
      memberIds: edge.memberIds || [edge.id],
    };
  }

  function flowJourneyGraph(context) {
    const graph = flowGraph(context);
    if (!context.flowJourney.length || context.callTrace) return graph;
    const journeyNodeIds = new Set(context.flowJourney.map((step) => step.nodeId));
    const nodeIds = new Set(journeyNodeIds);
    const activeNodeId = flowActiveNodeId(context.flowJourney);
    if (context.inlineExpanded.has(activeNodeId)) {
      children(context, activeNodeId).forEach((child) => {
        if (!context.hiddenGraphNodes.has(child.id)) nodeIds.add(child.id);
      });
    }
    const edgeIds = new Set();
    graph.edges.forEach((edge) => {
      const touchesJourney = journeyNodeIds.has(edge.source) || journeyNodeIds.has(edge.target);
      const connectsRetainedNodes = nodeIds.has(edge.source) && nodeIds.has(edge.target);
      if (touchesJourney) {
        nodeIds.add(edge.source);
        nodeIds.add(edge.target);
        edgeIds.add(edge.id);
      } else if (edge.kind === "contains" && connectsRetainedNodes) {
        edgeIds.add(edge.id);
      }
    });
    const nodes = new Map(graph.nodes.filter((graphNode) => nodeIds.has(graphNode.id)).map((graphNode) => [graphNode.id, graphNode]));
    journeyNodeIds.forEach((nodeId) => {
      const graphNode = node(context, nodeId);
      if (graphNode && !context.hiddenGraphNodes.has(nodeId)) nodes.set(nodeId, { ...graphNode, context: false, journey: true });
    });
    const edges = new Map(graph.edges.filter((edge) => edgeIds.has(edge.id)).map((edge) => [edge.id, edge]));
    context.flowJourney.forEach((step) => {
      if (!step.relation || !nodes.has(step.relation.source) || !nodes.has(step.relation.target)) return;
      const relationId = step.relation.id || `journey:${step.fromNodeId}:${step.nodeId}`;
      edges.set(relationId, {
        ...step.relation,
        id: relationId,
        aggregate: step.relation.memberIds.length > 1,
        memberIds: step.relation.memberIds,
        journey: true,
      });
    });
    return {
      nodes: [...nodes.values()],
      edges: [...edges.values()].filter((edge) => nodes.has(edge.source) && nodes.has(edge.target)),
    };
  }

  const api = Object.freeze({
    callTraceGraph,
    canEnterScope,
    descendantIds,
    flowActiveNodeId,
    flowGraph,
    flowJourneyGraph,
    flowRelationSnapshot,
    focusGraph,
    highlightedGraph,
    isDescendant,
    outgoingCallTrace,
    structureGraph,
    visibleHierarchyNodes,
  });
  globalScope.HeroGraphViews = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis === "undefined" ? this : globalThis);
