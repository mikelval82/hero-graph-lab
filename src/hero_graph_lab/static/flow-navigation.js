((globalScope) => {
  function normalizeRelation(relation) {
    if (!relation?.source || !relation?.target) return null;
    return {
      id: relation.id || null,
      source: relation.source,
      target: relation.target,
      kind: relation.kind || "custom",
      label: relation.label || "",
      status: relation.status || "observed",
      memberIds: Array.isArray(relation.memberIds) ? [...relation.memberIds] : relation.id ? [relation.id] : [],
    };
  }

  function createStep(nodeId, { fromNodeId = null, relation = null, expanded = false } = {}) {
    if (!nodeId) return null;
    const normalizedRelation = normalizeRelation(relation);
    const direction = normalizedRelation && fromNodeId
      ? normalizedRelation.source === fromNodeId && normalizedRelation.target === nodeId ? "forward" : "reverse"
      : null;
    return { nodeId, fromNodeId, relation: normalizedRelation, direction, expanded: Boolean(expanded) };
  }

  function normalizeJourney(journey) {
    if (!Array.isArray(journey)) return [];
    return journey.map((step) => createStep(step?.nodeId, step || {})).filter(Boolean);
  }

  function appendStep(journey, nodeId, options = {}) {
    const normalized = normalizeJourney(journey);
    const current = normalized.at(-1);
    if (current?.nodeId === nodeId) {
      current.expanded ||= Boolean(options.expanded);
      return normalized;
    }
    const step = createStep(nodeId, options);
    return step ? [...normalized, step] : normalized;
  }

  function truncateJourney(journey, index) {
    return normalizeJourney(journey).slice(0, Math.max(0, index + 1));
  }

  function migrateLegacyJourney(flowOrigin, flowTrail) {
    const nodeIds = [flowOrigin, ...(Array.isArray(flowTrail) ? flowTrail : [])].filter(Boolean);
    return nodeIds.filter((nodeId, index) => nodeIds.indexOf(nodeId) === index).map((nodeId, index) => createStep(nodeId, {
      fromNodeId: index ? nodeIds[index - 1] : null,
      expanded: index > 0,
    }));
  }

  function pruneJourney(journey, invalidNodeIds) {
    const invalid = invalidNodeIds instanceof Set ? invalidNodeIds : new Set(invalidNodeIds || []);
    const firstInvalid = normalizeJourney(journey).findIndex((step) => invalid.has(step.nodeId));
    return firstInvalid < 0 ? normalizeJourney(journey) : normalizeJourney(journey).slice(0, firstInvalid);
  }

  const api = { appendStep, createStep, migrateLegacyJourney, normalizeJourney, pruneJourney, truncateJourney };
  globalScope.HeroFlowNavigation = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis === "undefined" ? this : globalThis);