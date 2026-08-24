const assert = require("node:assert/strict");
const test = require("node:test");

const { graphMinimumSize } = require("../src/hero_graph_lab/static/graph-render.js");

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
