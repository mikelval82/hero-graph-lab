const assert = require("node:assert/strict");
const test = require("node:test");

const {
  appendStep,
  migrateLegacyJourney,
  pruneJourney,
  truncateJourney,
} = require("../src/hero_graph_lab/static/flow-navigation.js");

test("appends directed relational steps without replacing earlier branches", () => {
  let journey = appendStep([], "bootstrap");
  journey = appendStep(journey, "pricing", {
    fromNodeId: "bootstrap",
    relation: { id: "calls-pricing", source: "bootstrap", target: "pricing", kind: "calls" },
  });
  journey = appendStep(journey, "domain", {
    fromNodeId: "pricing",
    relation: { id: "calls-domain", source: "pricing", target: "domain", kind: "calls" },
  });

  assert.deepEqual(journey.map((step) => step.nodeId), ["bootstrap", "pricing", "domain"]);
  assert.deepEqual(journey.slice(1).map((step) => step.relation.kind), ["calls", "calls"]);
  assert.deepEqual(journey.slice(1).map((step) => step.direction), ["forward", "forward"]);
});

test("records reverse traversal and repeated nodes", () => {
  let journey = appendStep([], "subtotal");
  journey = appendStep(journey, "discount", {
    fromNodeId: "subtotal",
    relation: { id: "discount-subtotal", source: "discount", target: "subtotal", kind: "calls" },
  });
  journey = appendStep(journey, "subtotal", {
    fromNodeId: "discount",
    relation: { id: "discount-subtotal", source: "discount", target: "subtotal", kind: "calls" },
  });

  assert.equal(journey[1].direction, "reverse");
  assert.equal(journey[2].direction, "forward");
  assert.deepEqual(journey.map((step) => step.nodeId), ["subtotal", "discount", "subtotal"]);
});

test("truncates and prunes a journey at the requested boundary", () => {
  const journey = ["a", "b", "c", "d"].reduce((steps, nodeId) => appendStep(steps, nodeId), []);

  const truncated = truncateJourney(journey, 1);
  const pruned = pruneJourney(journey, new Set(["c"]));

  assert.deepEqual(truncated.map((step) => step.nodeId), ["a", "b"]);
  assert.deepEqual(pruned.map((step) => step.nodeId), ["a", "b"]);
  assert.equal(journey.length, 4);
});

test("migrates the legacy origin and hierarchy trail once", () => {
  const journey = migrateLegacyJourney("bootstrap", ["pricing", "policy", "PricingPolicy"]);

  assert.deepEqual(journey.map((step) => step.nodeId), ["bootstrap", "pricing", "policy", "PricingPolicy"]);
  assert.equal(journey[0].expanded, false);
  assert.equal(journey[1].expanded, true);
  assert.equal(journey[1].relation, null);
});