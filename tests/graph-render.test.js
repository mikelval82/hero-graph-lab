const assert = require("node:assert/strict");
const test = require("node:test");

const { focusColumnPositions, focusLayoutStrategy, graphMinimumSize } = require("../src/hero_graph_lab/static/graph-render.js");

test("normal graph layouts preserve their existing minimum dimensions", () => {
  assert.deepEqual(graphMinimumSize({ viewportWidth: 1800, viewportHeight: 900 }), { width: 1000, height: 680 });
  assert.deepEqual(graphMinimumSize({ compact: true, viewportWidth: 800, viewportHeight: 600 }), { width: 600, height: 680 });
});

test("G projection layouts consume the focused viewport inside Fit padding", () => {
  assert.deepEqual(
    graphMinimumSize({ projectionActive: true, viewportWidth: 1800, viewportHeight: 900, fitPadding: 32 }),
    { width: 1768, height: 868 },
  );
});

test("G projection layouts retain usable fallbacks for small or unavailable viewports", () => {
  assert.deepEqual(
    graphMinimumSize({ projectionActive: true, viewportWidth: 0, viewportHeight: 0 }),
    { width: 1000, height: 680 },
  );
  assert.deepEqual(
    graphMinimumSize({ projectionActive: true, compact: true, viewportWidth: 420, viewportHeight: 360 }),
    { width: 600, height: 480 },
  );
});

test("normal Focus retains its compact fixed-gap columns", () => {
  assert.deepEqual(
    focusColumnPositions({ width: 1600, columnGap: 220, maxWidth: 180, incomingCount: 2, outgoingCount: 3 }),
    { selected: 800, incoming: 580, outgoing: 1020 },
  );
});

test("projected Focus distributes two-sided collaborators across the canvas", () => {
  assert.deepEqual(
    focusColumnPositions({ width: 1600, columnGap: 220, maxWidth: 180, projectionActive: true, incomingCount: 2, outgoingCount: 3 }),
    { selected: 800, incoming: 138, outgoing: 1462 },
  );
});

test("projected Focus uses opposite columns for one-sided collaborators", () => {
  assert.deepEqual(
    focusColumnPositions({ width: 1600, columnGap: 220, maxWidth: 180, projectionActive: true, outgoingCount: 3 }),
    { selected: 138, incoming: 138, outgoing: 1462 },
  );
  assert.deepEqual(
    focusColumnPositions({ width: 1600, columnGap: 220, maxWidth: 180, projectionActive: true, incomingCount: 2 }),
    { selected: 1462, incoming: 138, outgoing: 1462 },
  );
});

test("projected Focus keeps direct neighborhoods in the wide Focus layout", () => {
  assert.equal(focusLayoutStrategy({
    projectionActive: true,
    selectedId: "selected",
    nodes: [{ id: "incoming" }, { id: "selected" }, { id: "outgoing" }],
    edges: [
      { source: "incoming", target: "selected" },
      { source: "selected", target: "outgoing" },
    ],
  }), "focus");
});

test("projected Focus uses total Flow geometry when indirect nodes are present", () => {
  assert.equal(focusLayoutStrategy({
    projectionActive: true,
    selectedId: "selected",
    nodes: [{ id: "selected" }, { id: "direct" }, { id: "indirect" }],
    edges: [
      { source: "selected", target: "direct" },
      { source: "direct", target: "indirect" },
    ],
  }), "flow");
  assert.equal(focusLayoutStrategy({
    selectedId: "selected",
    nodes: [{ id: "selected" }, { id: "direct" }, { id: "indirect" }],
    edges: [{ source: "selected", target: "direct" }],
  }), "focus");
});
