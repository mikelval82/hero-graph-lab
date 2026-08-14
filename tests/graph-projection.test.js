const assert = require("node:assert/strict");
const test = require("node:test");

const {
  backState,
  createProjection,
  expandState,
  normalizeGraph,
  replaceDepth,
  restoreView,
} = require("../src/hero_graph_lab/static/graph-projection.js");

const nodes = {
  root: { id: "root", kind: "module", label: "Root", context: true },
  alpha: { id: "alpha", kind: "function", label: "Alpha", context: true },
  beta: { id: "beta", kind: "function", label: "Beta", context: true },
  unrelated: { id: "unrelated", kind: "function", label: "Unrelated", context: true },
};

const edges = {
  rootAlpha: { id: "root-alpha", source: "root", target: "alpha", kind: "contains" },
  alphaBeta: { id: "alpha-beta", source: "alpha", target: "beta", kind: "calls" },
};

function graph(nodeIds, graphEdges = []) {
  return { nodes: nodeIds.map((id) => nodes[id]), edges: graphEdges };
}

function returnView() {
  return {
    view: "flow",
    positions: { root: { x: 10, y: 20 } },
    currentLayout: { projectionKey: "root", positions: { root: { x: 10, y: 20 } }, width: 800, height: 600 },
    viewStates: { structure: null, flow: { selected: "root" }, focus: null },
    graphZoom: 1.25,
    scrollLeft: 17,
    scrollTop: 23,
    selected: "root",
    selectedRelation: "root-alpha",
    layoutLocked: true,
    layoutSnapshot: { width: 800, height: 600, positions: { root: { x: 10, y: 20 } } },
  };
}

function initialProjection() {
  return createProjection({
    recommendation: {
      type: "hierarchy",
      label: "Package hierarchy",
      view: "flow",
      options: { anchorId: "root" },
    },
    depth: 1,
    graph: graph(["root"]),
    activeAnchor: "root",
    returnView: returnView(),
  });
}

test("normalizes a projection without mutating generator output", () => {
  const source = graph(["root", "alpha"], [{ source: "root", target: "alpha", kind: "contains" }]);
  const normalized = normalizeGraph(source);

  assert.equal(normalized.nodes.every((node) => node.context === false), true);
  assert.equal(normalized.edges[0].id, "projection:root:contains:alpha");
  assert.deepEqual(normalized.edges[0].memberIds, []);
  assert.equal(source.nodes[0].context, true);
  assert.equal(source.edges[0].id, undefined);
});

test("expands consecutive nodes and Back restores the exact preceding step", () => {
  const initial = initialProjection();
  const first = expandState(initial, {
    anchorId: "root",
    addition: graph(["root", "alpha"], [edges.rootAlpha]),
    viewState: { currentLayout: { projectionKey: "root" }, graphZoom: 1, scrollLeft: 5, scrollTop: 6 },
  });
  const second = expandState(first.projection, {
    anchorId: "alpha",
    addition: graph(["alpha", "beta"], [edges.alphaBeta]),
    viewState: { currentLayout: { projectionKey: "root|alpha" }, graphZoom: 1.4, scrollLeft: 30, scrollTop: 40 },
  });

  assert.equal(first.changed, true);
  assert.equal(second.changed, true);
  assert.deepEqual(second.projection.graph.nodes.map((node) => node.id), ["root", "alpha", "beta"]);
  assert.equal(second.projection.graph.nodes.some((node) => node.id === "unrelated"), false);
  assert.equal(second.projection.history.length, 2);

  const back = backState(second.projection);
  assert.equal(back.kind, "back");
  assert.deepEqual(back.projection.graph, first.projection.graph);
  assert.equal(back.projection.activeAnchor, "root");
  assert.equal(back.projection.history.length, 1);
  assert.deepEqual(back.projection.savedLayout, { projectionKey: "root|alpha" });
  assert.equal(back.previous.graphZoom, 1.4);
  assert.equal(back.previous.scrollLeft, 30);
  assert.equal(back.previous.scrollTop, 40);
});

test("reports a no-op expansion without creating history", () => {
  const projection = initialProjection();
  const result = expandState(projection, {
    anchorId: "root",
    addition: graph(["root"]),
    viewState: { currentLayout: null, graphZoom: 1, scrollLeft: 0, scrollTop: 0 },
  });

  assert.equal(result.changed, false);
  assert.equal(result.projection, projection);
  assert.equal(result.projection.history.length, 0);
});

test("depth replacement discards expanded context and history", () => {
  const expanded = expandState(initialProjection(), {
    anchorId: "root",
    addition: graph(["root", "alpha", "unrelated"], [edges.rootAlpha]),
    viewState: { currentLayout: { projectionKey: "expanded" }, graphZoom: 1, scrollLeft: 0, scrollTop: 0 },
  }).projection;

  const replaced = replaceDepth(expanded, {
    depth: 2,
    graph: graph(["root", "beta"]),
    activeAnchor: "root",
  });

  assert.equal(replaced.depth, 2);
  assert.deepEqual(replaced.graph.nodes.map((node) => node.id), ["root", "beta"]);
  assert.equal(replaced.history.length, 0);
  assert.equal(replaced.savedLayout, null);
  assert.deepEqual(expanded.graph.nodes.map((node) => node.id), ["root", "alpha", "unrelated"]);
});

test("restore returns a deep copy of the complete pre-projection view", () => {
  const expected = returnView();
  const projection = initialProjection();
  const restored = restoreView(projection);

  assert.deepEqual(restored, expected);
  assert.notEqual(restored, projection.returnView);
  restored.positions.root.x = 999;
  restored.viewStates.flow.selected = "changed";
  assert.equal(projection.returnView.positions.root.x, 10);
  assert.equal(projection.returnView.viewStates.flow.selected, "root");
});

test("Back requests full Restore when projection history is empty", () => {
  const projection = initialProjection();
  const result = backState(projection);

  assert.equal(result.kind, "restore");
  assert.equal(result.projection, projection);
});
