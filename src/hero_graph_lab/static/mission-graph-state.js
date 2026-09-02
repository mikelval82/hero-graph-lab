function differsInFields(left, right, fields) {
  return fields.some((field) => JSON.stringify(left?.[field] ?? null) !== JSON.stringify(right?.[field] ?? null));
}

function copyFields(target, source, fields) {
  fields.forEach((field) => {
    if (field in source) target[field] = structuredClone(source[field]);
  });
}

const LOCAL_NODE_FIELDS = [
  "label", "kind", "parent", "status", "previousStatus", "designDescription",
  "target_path", "qualified_name", "signature", "docstring", "satisfies", "acceptance",
  "designProvenance",
];
const LOCAL_EDGE_FIELDS = ["source", "target", "kind", "label", "properties", "status", "previousStatus", "designProvenance"];

function applyLocalDraft(graph, baseline, draft) {
  const baseNodes = new Map((baseline.nodes || []).map((node) => [node.id, node]));
  const draftNodes = new Map((draft.nodes || []).map((node) => [node.id, node]));
  const nodes = new Map(graph.nodes.map((node) => [node.id, node]));
  draftNodes.forEach((node, id) => {
    const previous = baseNodes.get(id);
    const current = nodes.get(id);
    if (!previous && !current) {
      graph.nodes.push(structuredClone(node));
      nodes.set(id, graph.nodes.at(-1));
    } else if (previous && current && differsInFields(previous, node, LOCAL_NODE_FIELDS)) {
      copyFields(current, node, LOCAL_NODE_FIELDS);
    }
  });
  baseNodes.forEach((node, id) => {
    if (node.status === "proposed" && !draftNodes.has(id)) {
      graph.nodes = graph.nodes.filter((candidate) => candidate.id !== id);
      nodes.delete(id);
    }
  });

  const edgeKey = (edge) => edge.id || edge.designKey || `${edge.source}|${edge.target}|${edge.kind}`;
  const baseEdges = new Map((baseline.edges || []).map((edge) => [edgeKey(edge), edge]));
  const draftEdges = new Map((draft.edges || []).map((edge) => [edgeKey(edge), edge]));
  const edges = new Map(graph.edges.map((edge) => [edgeKey(edge), edge]));
  draftEdges.forEach((edge, key) => {
    const previous = baseEdges.get(key);
    const current = edges.get(key);
    if (!previous && !current && nodes.has(edge.source) && nodes.has(edge.target)) {
      graph.edges.push(structuredClone(edge));
      edges.set(key, graph.edges.at(-1));
    } else if (previous && current && differsInFields(previous, edge, LOCAL_EDGE_FIELDS)) {
      copyFields(current, edge, LOCAL_EDGE_FIELDS);
    }
  });
  baseEdges.forEach((edge, key) => {
    if (edge.status === "proposed" && !draftEdges.has(key)) graph.edges = graph.edges.filter((candidate) => edgeKey(candidate) !== key);
  });
  graph.edges = graph.edges.filter((edge) => nodes.has(edge.source) && nodes.has(edge.target));
  return graph;
}

function normalizeMissionDesignEdge(designEdge, sourceId, targetId, realization = null, index = 0) {
  const relation = String(designEdge.relation || "custom").trim() || "custom";
  return {
    id: `design:${index}:${designEdge.source}:${designEdge.target}`,
    source: sourceId,
    target: targetId,
    kind: "custom",
    label: relation,
    properties: {},
    designKey: `${designEdge.source}|${designEdge.target}|${designEdge.relation}`,
    designIntent: designEdge.intent,
    designProvenance: designEdge.provenance || "AGENT",
    realization,
    status: realization?.status === "accepted"
      ? "accepted"
      : ({ KEEP: "observed", CREATE: "proposed", CHANGE: "modified", REMOVE: "removed" }[designEdge.intent] || "observed"),
  };
}

function isSemanticMissionRoot(designNode) {
  return !designNode.parent_id
    && !designNode.locator
    && ["SYSTEM", "PACKAGE"].includes(designNode.level);
}

function packageMissionLocator(graph, node) {
  if (node?.kind !== "package") return null;
  const labels = [];
  const byId = new Map((graph.nodes || []).map((candidate) => [candidate.id, candidate]));
  let current = node;
  while (current?.kind === "package") {
    if (current.parent) labels.unshift(current.label);
    current = byId.get(current.parent);
  }
  return labels.length ? labels.join("/") : null;
}

const api = { applyLocalDraft, isSemanticMissionRoot, normalizeMissionDesignEdge, packageMissionLocator };
if (typeof module !== "undefined" && module.exports) module.exports = api;
if (typeof globalThis !== "undefined") globalThis.HeroMissionGraphState = api;
