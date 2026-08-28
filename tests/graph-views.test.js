const assert = require("node:assert/strict");
const test = require("node:test");

const {
  callTraceGraph,
  descendantIds,
  flowGraph,
  flowJourneyGraph,
  focusGraph,
  highlightedGraph,
  isDescendant,
  outgoingCallTrace,
  structureGraph,
  visibleHierarchyNodes,
} = require("../src/hero_graph_lab/static/graph-views.js");

const graph = {
  root: "root",
  nodes: [
    { id: "root", kind: "package", label: "Root", parent: null },
    { id: "module-a", kind: "module", label: "Module A", parent: "root" },
    { id: "module-b", kind: "module", label: "Module B", parent: "root" },
    { id: "module-c", kind: "module", label: "Module C", parent: "root" },
    { id: "class-a", kind: "class", label: "Class A", parent: "module-a" },
    { id: "class-b", kind: "class", label: "Class B", parent: "module-b" },
    { id: "func-a", kind: "method", label: "func_a", parent: "class-a" },
    { id: "func-b", kind: "method", label: "func_b", parent: "class-b" },
  ],
  edges: [
    { id: "root-a", source: "root", target: "module-a", kind: "contains" },
    { id: "root-b", source: "root", target: "module-b", kind: "contains" },
    { id: "root-c", source: "root", target: "module-c", kind: "contains" },
    { id: "a-class", source: "module-a", target: "class-a", kind: "contains" },
    { id: "b-class", source: "module-b", target: "class-b", kind: "contains" },
    { id: "a-func", source: "class-a", target: "func-a", kind: "contains" },
    { id: "b-func", source: "class-b", target: "func-b", kind: "contains" },
    { id: "call-ab", source: "func-a", target: "func-b", kind: "calls", status: "observed" },
    { id: "call-removed", source: "func-b", target: "func-a", kind: "calls", status: "removed" },
  ],
};

function context(overrides = {}) {
  const nodeById = new Map(graph.nodes.map((node) => [node.id, node]));
  const childrenByParent = new Map();
  graph.nodes.forEach((node) => {
    if (!childrenByParent.has(node.parent)) childrenByParent.set(node.parent, []);
    childrenByParent.get(node.parent).push(node);
  });
  return {
    graph,
    scope: "root",
    selected: null,
    inlineExpanded: new Set(),
    hiddenGraphNodes: new Set(),
    callTrace: null,
    flowJourney: [],
    nodeById,
    childrenByParent,
    ...overrides,
  };
}

test("hierarchy views honor explicit expansion and hidden-node inputs", () => {
  const viewContext = context({
    inlineExpanded: new Set(["module-a"]),
    hiddenGraphNodes: new Set(["module-b"]),
  });
  const hierarchy = visibleHierarchyNodes(viewContext);
  const structure = structureGraph(viewContext);

  assert.deepEqual(hierarchy.map((node) => node.id), ["module-a", "class-a", "module-c"]);
  assert.equal(hierarchy.every((node) => node.context === false), true);
  assert.deepEqual(structure.nodes, hierarchy);
  assert.deepEqual(structure.edges.map((edge) => edge.id), ["a-class"]);
  assert.deepEqual([...viewContext.inlineExpanded], ["module-a"]);
});

test("Flow aggregates deep relations at their visible representatives", () => {
  const flow = flowGraph(context());
  const call = flow.edges.find((edge) => edge.kind === "calls");

  assert.deepEqual(flow.nodes.map((node) => node.id), ["module-a", "module-b", "module-c"]);
  assert.equal(call.source, "module-a");
  assert.equal(call.target, "module-b");
  assert.equal(call.aggregate, true);
  assert.deepEqual(call.memberIds, ["call-ab"]);
});

test("Focus returns the selected node, call neighbors, and visible removed relations", () => {
  const focus = focusGraph(context({ selected: "module-a" }));

  assert.deepEqual(focus.nodes.map((node) => node.id), ["module-a", "module-b"]);
  assert.equal(focus.edges.length, 2);
  assert.equal(focus.edges.every((edge) => edge.kind === "calls"), true);
  assert.deepEqual(focus.edges.map((edge) => edge.status).sort(), ["observed", "removed"]);
});

test("highlight-only view retains the selection and its exact visible neighbors", () => {
  const flow = flowGraph(context());
  const original = structuredClone(flow);
  const highlighted = highlightedGraph(flow, "module-a");

  assert.deepEqual(highlighted.nodes.map((node) => node.id), ["module-a", "module-b"]);
  assert.deepEqual(highlighted.edges.map((edge) => edge.kind), ["calls", "calls"]);
  assert.deepEqual(flow, original);
  assert.equal(highlightedGraph(flow, null), flow);
});

test("call tracing follows outgoing active calls to the requested depth", () => {
  const trace = outgoingCallTrace(graph, "func-a", 2);
  const tracedGraph = callTraceGraph(context({ callTrace: trace }));

  assert.deepEqual([...trace.nodeDepths], [["func-a", 0], ["func-b", 1]]);
  assert.deepEqual([...trace.edgeIds], ["call-ab"]);
  assert.deepEqual(tracedGraph.nodes.map((node) => [node.id, node.traceDepth]), [["func-a", 0], ["func-b", 1]]);
  assert.deepEqual(tracedGraph.edges.map((edge) => edge.id), ["call-ab"]);
});

test("journey view retains the directed path and removes unrelated visible nodes", () => {
  const relation = {
    id: "aggregate:root:module-a:calls:module-b:observed",
    source: "module-a",
    target: "module-b",
    kind: "calls",
    label: "calls",
    status: "observed",
    memberIds: ["call-ab"],
  };
  const journey = flowJourneyGraph(context({
    flowJourney: [
      { nodeId: "module-a", fromNodeId: null, relation: null, expanded: false },
      { nodeId: "module-b", fromNodeId: "module-a", relation, expanded: false },
    ],
  }));

  assert.deepEqual(journey.nodes.map((node) => node.id), ["module-a", "module-b"]);
  assert.equal(journey.nodes.every((node) => node.journey), true);
  assert.deepEqual(journey.edges.map((edge) => edge.id), [
    relation.id,
    "aggregate:root:module-b:calls:module-a:removed",
  ]);
  assert.equal(journey.edges.find((edge) => edge.id === relation.id).journey, true);
});

test("ancestry helpers derive descendants without mutating indexes", () => {
  const viewContext = context();
  assert.equal(isDescendant(viewContext, "func-a", "module-a"), true);
  assert.equal(isDescendant(viewContext, "module-b", "module-a"), false);
  assert.deepEqual([...descendantIds(viewContext, "module-a")].sort(), ["class-a", "func-a"]);
  assert.equal(viewContext.childrenByParent.get("module-a").length, 1);
});
