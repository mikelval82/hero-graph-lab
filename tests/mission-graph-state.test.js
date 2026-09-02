const assert = require("node:assert/strict");
const test = require("node:test");

const { applyLocalDraft, isSemanticMissionRoot, normalizeMissionDesignEdge } = require("../src/hero_graph_lab/static/mission-graph-state.js");

test("recognizes semantic package roots used by mission designs", () => {
  assert.equal(isSemanticMissionRoot({ level: "PACKAGE", parent_id: null, locator: null }), true);
  assert.equal(isSemanticMissionRoot({ level: "CODE", parent_id: null, locator: null }), false);
  assert.equal(isSemanticMissionRoot({ level: "PACKAGE", parent_id: "root", locator: null }), false);
});

test("normalizes mission relations for the visual graph", () => {
  const edge = normalizeMissionDesignEdge(
    { source: "a", target: "b", relation: "dispatches markdown files to", intent: "KEEP", provenance: "AGENT" },
    "observed:a",
    "proposal:b",
  );

  assert.equal(edge.kind, "custom");
  assert.equal(edge.label, "dispatches markdown files to");
  assert.equal(edge.status, "observed");
  assert.equal(edge.designProvenance, "AGENT");
});

test("keeps remote mission changes while applying only the local draft delta", () => {
  const baseline = {
    nodes: [
      { id: "observed:service", label: "Service", kind: "class", status: "observed" },
    ],
    edges: [],
  };
  const remote = {
    nodes: [
      { id: "observed:service", label: "Service", kind: "class", status: "modified", designDescription: "Remote design" },
      { id: "mission:worker", label: "Worker", kind: "class", status: "proposed" },
    ],
    edges: [],
  };
  const localDraft = {
    nodes: [
      { id: "observed:service", label: "Service", kind: "class", status: "modified", designDescription: "Local draft" },
      { id: "local:adapter", label: "Adapter", kind: "class", status: "proposed" },
    ],
    edges: [
      { id: "local-edge", source: "observed:service", target: "local:adapter", kind: "uses", status: "proposed" },
    ],
  };

  const graph = applyLocalDraft(structuredClone(remote), baseline, localDraft);

  assert.equal(graph.nodes.find((node) => node.id === "observed:service").designDescription, "Local draft");
  assert.ok(graph.nodes.some((node) => node.id === "mission:worker"));
  assert.ok(graph.nodes.some((node) => node.id === "local:adapter"));
  assert.ok(graph.edges.some((edge) => edge.id === "local-edge"));
});

test("does not reintroduce a local proposed node that was removed from its draft", () => {
  const baseline = { nodes: [{ id: "proposal:old", status: "proposed" }], edges: [] };
  const remote = { nodes: [{ id: "proposal:old", status: "proposed" }, { id: "remote", status: "proposed" }], edges: [] };

  const graph = applyLocalDraft(structuredClone(remote), baseline, { nodes: [], edges: [] });

  assert.deepEqual(graph.nodes.map((node) => node.id), ["remote"]);
});
