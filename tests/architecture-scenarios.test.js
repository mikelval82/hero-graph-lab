const assert = require("node:assert/strict");
const test = require("node:test");

require("../src/hero_graph_lab/static/proposal-contract.js");
const { draftSnapshot, impactLines } = require("../src/hero_graph_lab/static/architecture-scenarios.js");


test("captures only design nodes, design relations, and referenced observed endpoints", () => {
  const graph = {
    nodes: [
      { id: "root", label: "Project", kind: "package", status: "observed", source: "" },
      { id: "observed:server", label: "server.py", kind: "module", parent: "root", status: "observed", source: "src/server.py" },
      { id: "observed:unrelated", label: "unused.py", kind: "module", parent: "root", status: "observed", source: "src/unused.py" },
      {
        id: "proposal:scenario",
        label: " ArchitectureScenarioService ",
        kind: "class",
        parent: "root",
        status: "proposed",
        designDescription: " Compare immutable alternatives. ",
        target_path: " src\\architecture\\scenarios.py ",
        qualified_name: " ArchitectureScenarioService ",
        docstring: " Compare alternatives. ",
        satisfies: ["AW-003"],
        acceptance: ["Reports exact changes."],
      },
    ],
    edges: [
      { id: "observed-containment", source: "root", target: "observed:server", kind: "contains", status: "observed" },
      { id: "design-anchor", source: "proposal:scenario", target: "observed:server", kind: "integrates_with", label: " exposes API ", status: "proposed", properties: { evidence: "server.py" } },
    ],
  };

  const captured = draftSnapshot(graph);

  assert.deepEqual(captured.nodes, [{
    id: "proposal:scenario",
    label: "ArchitectureScenarioService",
    kind: "class",
    parent: "root",
    status: "proposed",
    description: "Compare immutable alternatives.",
    target_path: "src/architecture/scenarios.py",
    qualified_name: "ArchitectureScenarioService",
    signature: "",
    docstring: "Compare alternatives.",
    satisfies: ["AW-003"],
    acceptance: ["Reports exact changes."],
  }]);
  assert.deepEqual(captured.edges, [{
    source: "proposal:scenario",
    target: "observed:server",
    kind: "integrates_with",
    label: "exposes API",
    status: "proposed",
    properties: { evidence: "server.py" },
  }]);
  assert.deepEqual(captured.observed_endpoints.map((node) => node.id), ["observed:server", "root"]);
  assert.equal(captured.observed_endpoints.some((node) => node.id === "observed:unrelated"), false);
  assert.equal(graph.nodes[3].label, " ArchitectureScenarioService ");
  assert.equal(graph.edges[1].label, " exposes API ");
});


test("captures modified and removed observed elements as design changes", () => {
  const graph = {
    nodes: [
      { id: "modified", label: "Service", kind: "class", status: "modified", description: "New responsibility" },
      { id: "removed", label: "Legacy", kind: "module", status: "removed" },
      { id: "observed", label: "Observed", kind: "module", status: "observed" },
    ],
    edges: [
      { source: "modified", target: "observed", kind: "uses", status: "modified", properties: {} },
      { source: "removed", target: "observed", kind: "calls", status: "removed", properties: {} },
    ],
  };

  const captured = draftSnapshot(graph);

  assert.deepEqual(captured.nodes.map((node) => node.id), ["modified", "removed"]);
  assert.deepEqual(captured.edges.map((edge) => edge.status), ["modified", "removed"]);
  assert.deepEqual(captured.observed_endpoints.map((node) => node.id), ["observed"]);
});

test("captures accepted contract realizations without treating them as observed endpoints", () => {
  const captured = draftSnapshot({
    nodes: [{ id: "accepted", label: "Notifier", kind: "class", status: "accepted", target_path: "src/notifier.py" }],
    edges: [],
  });

  assert.deepEqual(captured.nodes.map((node) => node.status), ["accepted"]);
  assert.deepEqual(captured.observed_endpoints, []);
});


test("formats code anchors, dependent paths, and unresolved contracts", () => {
  const impact = {
    anchors: [{
      id: "module:demo.provider",
      label: "provider.py",
      kind: "module",
      source: "src/demo/provider.py",
      contract_node_ids: ["proposal:analyze"],
    }],
    dependents: [{
      id: "module:demo.consumer",
      label: "consumer.py",
      kind: "module",
      source: "src/demo/consumer.py",
      distance: 1,
      anchor_id: "module:demo.provider",
      path: [{
        source: "module:demo.consumer",
        source_label: "consumer.py",
        target: "module:demo.provider",
        target_label: "provider.py",
        kind: "depends_on",
      }],
    }],
    unresolved: [{ contract_node_id: "proposal:missing", reason: "no_observed_anchor" }],
  };

  assert.deepEqual(impactLines(impact), {
    anchors: ["provider.py · module · from proposal:analyze"],
    dependents: ["consumer.py · 1 hop · consumer.py -depends_on-> provider.py"],
    unresolved: ["proposal:missing · no observed anchor"],
  });
});
