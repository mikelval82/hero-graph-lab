const assert = require("node:assert/strict");
const test = require("node:test");

const {
  contractPayload,
  contractConnections,
  contractIssues,
  interfacePreview,
  normalizeContractNode,
} = require("../src/hero_graph_lab/static/proposal-contract.js");

test("serializes the exact HARNESS node contract without sharing mutable arrays", () => {
  const source = {
    kind: "method",
    designDescription: "Send a notification.",
    target_path: "src/telegram/gateway.py",
    qualified_name: "TelegramGateway.send_notification",
    signature: "(self, chat_id: str, text: str) -> str",
    docstring: "Send one notification.",
    satisfies: ["BR-002"],
    acceptance: ["Returns the provider id."],
  };

  const payload = contractPayload(source);

  assert.deepEqual(payload, {
    kind: "method",
    description: "Send a notification.",
    target_path: "src/telegram/gateway.py",
    qualified_name: "TelegramGateway.send_notification",
    signature: "(self, chat_id: str, text: str) -> str",
    docstring: "Send one notification.",
    satisfies: ["BR-002"],
    acceptance: ["Returns the provider id."],
  });
  source.satisfies.push("BR-003");
  source.acceptance.push("Retries once.");
  assert.deepEqual(payload.satisfies, ["BR-002"]);
  assert.deepEqual(payload.acceptance, ["Returns the provider id."]);
});

test("normalizes bounded proposal contract fields without guessing missing values", () => {
  const node = normalizeContractNode({
    id: "proposal:send",
    kind: "method",
    label: " send_notification ",
    target_path: " src\\telegram\\gateway.py ",
    qualified_name: " TelegramGateway.send_notification ",
    signature: " (self, chat_id: str, text: str) -> str ",
    docstring: " Send one notification. ",
    designDescription: " Telegram transport boundary. ",
    satisfies: [" BR-002 ", "BR-002", ""],
    acceptance: "Provider errors become TelegramTransportError.\nReturns the provider id.",
  });

  assert.equal(node.label, "send_notification");
  assert.equal(node.target_path, "src/telegram/gateway.py");
  assert.equal(node.qualified_name, "TelegramGateway.send_notification");
  assert.equal(node.signature, "(self, chat_id: str, text: str) -> str");
  assert.equal(node.docstring, "Send one notification.");
  assert.equal(node.designDescription, "Telegram transport boundary.");
  assert.deepEqual(node.satisfies, ["BR-002"]);
  assert.deepEqual(node.acceptance, [
    "Provider errors become TelegramTransportError.",
    "Returns the provider id.",
  ]);

  const legacy = normalizeContractNode({ id: "proposal:legacy", kind: "class", label: "Legacy" });
  assert.equal(legacy.target_path, "");
  assert.equal(legacy.signature, "");
  assert.deepEqual(legacy.acceptance, []);
});

test("derives a repository target path from an evidence-backed locator", () => {
  const node = normalizeContractNode({
    kind: "module",
    label: "markdown_adapter.py",
    locator: "src/hero_graph_lab/markdown_adapter.py",
  });

  assert.equal(node.target_path, "src/hero_graph_lab/markdown_adapter.py");
});

test("renders a Python-like class contract with child method declarations as text", () => {
  const graph = {
    nodes: [
      {
        id: "proposal:gateway",
        kind: "class",
        label: "TelegramGateway<script>",
        status: "proposed",
        target_path: "src/telegram/gateway.py",
        qualified_name: "TelegramGateway",
        docstring: "Transport <boundary>.",
      },
      {
        id: "proposal:send",
        kind: "method",
        label: "send_notification",
        parent: "proposal:gateway",
        status: "proposed",
        signature: "(self, chat_id: str, text: str) -> str",
        docstring: "Send one notification.",
      },
    ],
    edges: [],
  };

  const preview = interfacePreview(graph.nodes[0], graph);

  assert.match(preview, /class TelegramGateway:/);
  assert.match(preview, /"""Transport <boundary>\."""/);
  assert.match(preview, /def send_notification\(self, chat_id: str, text: str\) -> str:/);
  assert.match(preview, /"""Send one notification\."""/);
});

test("derives explicit observed anchors and does not count project-root containment", () => {
  const graph = {
    root: "root",
    nodes: [
      { id: "root", kind: "package", label: "Project", parent: null, status: "observed" },
      { id: "observed:module", kind: "module", label: "service.py", parent: "root", status: "observed", source: "src/service.py" },
      { id: "proposal:root", kind: "package", label: "Workbench", parent: "root", status: "proposed", designDescription: "Architecture tools" },
      { id: "proposal:impact", kind: "module", label: "Impact", parent: "proposal:root", status: "proposed", designDescription: "Impact analysis", target_path: "src/impact.py", acceptance: ["Explains affected nodes"] },
    ],
    edges: [
      { id: "placement", source: "root", target: "proposal:root", kind: "contains", status: "proposed" },
      { id: "internal", source: "proposal:root", target: "proposal:impact", kind: "contains", status: "proposed" },
    ],
  };

  assert.deepEqual(contractConnections("proposal:impact", graph).observedAnchors, []);
  assert.match(contractIssues(graph.nodes[3], graph).join("\n"), /No observed implementation connection/);

  graph.edges.push({
    id: "integration",
    source: "proposal:impact",
    target: "observed:module",
    kind: "depends_on",
    label: "reads extracted graph",
    status: "proposed",
  });

  const connections = contractConnections("proposal:root", graph);
  assert.deepEqual(connections.observedAnchors.map((item) => item.node.id), ["observed:module"]);
  assert.equal(connections.observedAnchors[0].relation.label, "reads extracted graph");
  assert.doesNotMatch(contractIssues(graph.nodes[3], graph).join("\n"), /No observed implementation connection/);
});

test("reports field-level incompleteness for legacy code proposals", () => {
  const node = { id: "proposal:legacy", kind: "method", label: "execute", status: "proposed" };
  const issues = contractIssues(node, { root: "root", nodes: [node], edges: [] });

  assert.deepEqual(issues, [
    "Add a responsibility description.",
    "Add an intended target path.",
    "Add a qualified name.",
    "Add a callable signature.",
    "Add a docstring.",
    "Add at least one acceptance criterion.",
    "No observed implementation connection.",
  ]);
});

test("reports invalid paths and signatures without rewriting the authored contract", () => {
  const node = {
    id: "proposal:invalid",
    kind: "function",
    label: "run",
    status: "proposed",
    designDescription: "Run one operation.",
    target_path: "../outside.py",
    qualified_name: "run",
    signature: "value: str",
    docstring: "Run it.",
    acceptance: ["Returns a result."],
  };

  const issues = contractIssues(node, { root: "root", nodes: [node], edges: [] });

  assert.match(issues.join("\n"), /repository-relative target path/);
  assert.match(issues.join("\n"), /signature beginning/);
  assert.equal(normalizeContractNode(node).target_path, "../outside.py");
});
