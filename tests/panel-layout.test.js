const assert = require("node:assert/strict");
const test = require("node:test");

const {
  defaultLayout,
  normalizeLayout,
  normalizeTypography,
  setPanelCollapsed,
} = require("../src/hero_graph_lab/static/panel-layout.js");

test("normalizes persisted layout and rejects unknown collapsed panels", () => {
  const normalized = normalizeLayout({
    explorerWidth: 320,
    graphRatio: 95,
    inspectorWidth: 275,
    collapsed: ["explorer", "unknown", "explorer", "code"],
  });

  assert.deepEqual(normalized, {
    explorerWidth: 320,
    graphRatio: 70,
    inspectorWidth: 275,
    collapsed: ["explorer", "code"],
  });
});

test("invalid persisted layout falls back to stable defaults", () => {
  assert.deepEqual(normalizeLayout(null), defaultLayout());
  assert.deepEqual(normalizeLayout("invalid"), defaultLayout());
  assert.deepEqual(normalizeLayout({ graphRatio: Number.NaN, collapsed: "explorer" }), defaultLayout());
});

test("normalizes typography within each panel limit", () => {
  assert.deepEqual(normalizeTypography({ explorer: 8, graph: 40, code: 18, inspector: 20 }), {
    explorer: 11,
    graph: 22,
    code: 18,
    inspector: 20,
  });
  assert.deepEqual(normalizeTypography(null), { explorer: 14, graph: 14, code: 14, inspector: 14 });
});

test("collapse transitions are immutable and preserve independent panels", () => {
  const original = { ...defaultLayout(), collapsed: ["explorer"] };
  const collapsed = setPanelCollapsed(original, "inspector", true);
  const expanded = setPanelCollapsed(collapsed, "explorer", false);

  assert.deepEqual(original.collapsed, ["explorer"]);
  assert.deepEqual(collapsed.collapsed, ["explorer", "inspector"]);
  assert.deepEqual(expanded.collapsed, ["inspector"]);
  assert.deepEqual(setPanelCollapsed(expanded, "unknown", true), expanded);
});
