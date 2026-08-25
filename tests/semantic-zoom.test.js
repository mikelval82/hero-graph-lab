const assert = require("node:assert/strict");
const test = require("node:test");

const {
  SemanticZoomProjector,
  semanticDetail,
  transitionSelection,
} = require("../src/hero_graph_lab/static/semantic-zoom.js");


const graph = {
  root: "root",
  source: "project",
  nodes: [
    { id: "root", kind: "package", label: "Project", parent: null, status: "observed" },
    { id: "area-a", kind: "package", label: "Orders", parent: "root", status: "observed" },
    { id: "module-a", kind: "module", label: "service.py", parent: "area-a", status: "observed" },
    { id: "class-a", kind: "class", label: "OrderService", parent: "module-a", status: "observed" },
    { id: "method-a", kind: "method", label: "place", parent: "class-a", status: "observed" },
    { id: "area-b", kind: "package", label: "Payments", parent: "root", status: "proposed" },
    { id: "module-b", kind: "module", label: "gateway.py", parent: "area-b", status: "proposed" },
    { id: "file-b", kind: "file", label: "client.js", parent: "area-b", status: "observed" },
    { id: "class-b", kind: "class", label: "PaymentGateway", parent: "module-b", status: "proposed" },
    { id: "method-b", kind: "method", label: "charge", parent: "class-b", status: "proposed" },
  ],
  edges: [
    { id: "root-a", source: "root", target: "area-a", kind: "contains", status: "observed", properties: {} },
    { id: "a-module", source: "area-a", target: "module-a", kind: "contains", status: "observed", properties: {} },
    { id: "a-class", source: "module-a", target: "class-a", kind: "contains", status: "observed", properties: {} },
    { id: "a-method", source: "class-a", target: "method-a", kind: "contains", status: "observed", properties: {} },
    { id: "root-b", source: "root", target: "area-b", kind: "contains", status: "proposed", properties: {} },
    { id: "b-module", source: "area-b", target: "module-b", kind: "contains", status: "proposed", properties: {} },
    { id: "b-file", source: "area-b", target: "file-b", kind: "contains", status: "observed", properties: {} },
    { id: "b-class", source: "module-b", target: "class-b", kind: "contains", status: "proposed", properties: {} },
    { id: "b-method", source: "class-b", target: "method-b", kind: "contains", status: "proposed", properties: {} },
    { id: "call-1", source: "method-a", target: "method-b", kind: "calls", label: "charges", status: "observed", properties: { protocol: "sync" } },
    { id: "call-2", source: "method-a", target: "method-b", kind: "calls", label: "charges", status: "observed", properties: { protocol: "sync" } },
    { id: "removed-call", source: "method-b", target: "method-a", kind: "calls", label: "legacy", status: "removed", properties: {} },
  ],
};

const projector = new SemanticZoomProjector();


test("projects explicit levels with stable source node identities", () => {
  const areas = projector.project(graph, { level: "areas", scopeId: "root", view: "flow", selectedId: "method-a" });
  const modules = projector.project(graph, { level: "modules", scopeId: "root", view: "flow", selectedId: "method-a" });
  const types = projector.project(graph, { level: "types", scopeId: "root", view: "flow", selectedId: "method-a" });
  const members = projector.project(graph, { level: "members", scopeId: "root", view: "flow", selectedId: "method-a" });

  assert.deepEqual(areas.nodes.map((node) => node.id), ["area-a", "area-b"]);
  assert.equal(areas.selectedId, "area-a");
  assert.deepEqual(
    areas.edges.find((edge) => edge.kind === "calls" && edge.status === "observed"),
    {
      id: "semantic:areas:0:area-a:calls:area-b",
      source: "area-a",
      target: "area-b",
      kind: "calls",
      status: "observed",
      label: "charges",
      properties: { protocol: "sync" },
      memberIds: ["call-1", "call-2"],
      count: 2,
      editLabel: "charges",
      aggregate: true,
    },
  );
  assert.deepEqual(modules.nodes.map((node) => node.id), ["area-a", "area-b", "file-b", "module-a", "module-b"]);
  assert.equal(modules.selectedId, "module-a");
  assert.equal(modules.nodes.some((node) => node.kind === "file"), true);
  assert.equal(types.nodes.some((node) => node.id === "class-a"), true);
  assert.equal(types.nodes.some((node) => node.id === "method-a"), false);
  assert.equal(types.selectedId, "class-a");
  assert.equal(members.nodes.some((node) => node.id === "method-a"), true);
  assert.equal(members.selectedId, "method-a");
});


test("projection is deterministic and does not mutate graph or option sets", () => {
  const reversed = {
    ...graph,
    nodes: [...graph.nodes].reverse(),
    edges: [...graph.edges].reverse(),
  };
  const hiddenNodeIds = new Set(["file-b"]);
  const before = JSON.stringify(graph);

  const first = projector.project(graph, { level: "modules", scopeId: "root", view: "flow", hiddenNodeIds });
  const second = projector.project(reversed, { level: "modules", scopeId: "root", view: "flow", hiddenNodeIds });

  assert.deepEqual(first, second);
  assert.equal(JSON.stringify(graph), before);
  assert.deepEqual([...hiddenNodeIds], ["file-b"]);
});


test("raw extracted relationships receive stable identities before app normalization", () => {
  const rawGraph = {
    ...graph,
    edges: graph.edges.map(({ id, ...edge }) => edge),
  };
  const reversed = {
    ...rawGraph,
    nodes: [...rawGraph.nodes].reverse(),
    edges: [...rawGraph.edges].reverse(),
  };

  const first = projector.project(rawGraph, { level: "modules", scopeId: "root", view: "flow" });
  const second = projector.project(reversed, { level: "modules", scopeId: "root", view: "flow" });

  assert.deepEqual(first, second);
  assert.equal(first.edges.every((edge) => edge.id && edge.memberIds.every(Boolean)), true);
});


test("hierarchy and focus retain their existing relationship semantics", () => {
  const hierarchy = projector.project(graph, { level: "types", scopeId: "root", view: "structure" });
  const focus = projector.project(graph, { level: "areas", scopeId: "root", view: "focus", selectedId: "method-a" });

  assert.equal(hierarchy.edges.every((edge) => edge.kind === "contains"), true);
  assert.deepEqual(focus.nodes.map((node) => node.id), ["area-a", "area-b"]);
  assert.equal(focus.edges.every((edge) => edge.kind === "calls"), true);
  assert.equal(focus.edges.some((edge) => edge.status === "removed"), true);
});


test("selection mapping restores the original member unless the user replaces it", () => {
  const mapSelection = (nodeId, level) => projector.project(
    graph,
    { level, scopeId: "root", view: "flow", selectedId: nodeId },
  ).selectedId;

  const coarse = transitionSelection({
    currentLevel: "native",
    nextLevel: "areas",
    selectedId: "method-a",
    rememberedSelection: null,
    mapSelection,
  });
  const types = transitionSelection({
    currentLevel: "areas",
    nextLevel: "types",
    selectedId: coarse.selectedId,
    rememberedSelection: coarse.rememberedSelection,
    mapSelection,
  });
  const restored = transitionSelection({
    currentLevel: "types",
    nextLevel: "native",
    selectedId: types.selectedId,
    rememberedSelection: types.rememberedSelection,
    mapSelection,
  });
  const userReplacement = transitionSelection({
    currentLevel: "areas",
    nextLevel: "native",
    selectedId: "area-b",
    rememberedSelection: coarse.rememberedSelection,
    mapSelection,
  });

  assert.deepEqual(coarse, {
    selectedId: "area-a",
    rememberedSelection: { sourceId: "method-a", mappedId: "area-a" },
  });
  assert.deepEqual(types, {
    selectedId: "class-a",
    rememberedSelection: { sourceId: "method-a", mappedId: "class-a" },
  });
  assert.deepEqual(restored, { selectedId: "method-a", rememberedSelection: null });
  assert.deepEqual(userReplacement, { selectedId: "area-b", rememberedSelection: null });
});


test("semantic detail thresholds change text detail without a topology decision", () => {
  assert.equal(semanticDetail(0.1), "overview");
  assert.equal(semanticDetail(0.449), "overview");
  assert.equal(semanticDetail(0.45), "context");
  assert.equal(semanticDetail(0.899), "context");
  assert.equal(semanticDetail(0.9), "detail");
  assert.equal(semanticDetail(2.5), "detail");
});
