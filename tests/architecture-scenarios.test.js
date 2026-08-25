const assert = require("node:assert/strict");
const test = require("node:test");

require("../src/hero_graph_lab/static/proposal-contract.js");
const { draftSnapshot } = require("../src/hero_graph_lab/static/architecture-scenarios.js");


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
