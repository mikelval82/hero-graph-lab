((globalScope) => {
  const DESIGN_STATUSES = new Set(["proposed", "modified", "removed", "accepted"]);

  function text(value, maximum = 500) {
    return String(value ?? "").trim().slice(0, maximum);
  }

  function cloneJson(value) {
    return JSON.parse(JSON.stringify(value ?? {}));
  }

  function draftSnapshot(graph = { nodes: [], edges: [] }) {
    const contractApi = globalScope.HeroProposalContract;
    if (!contractApi?.contractPayload) throw new Error("Proposal contract support is unavailable");
    const allNodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
    const allEdges = Array.isArray(graph?.edges) ? graph.edges : [];
    const designNodes = allNodes
      .filter((node) => DESIGN_STATUSES.has(node.status))
      .map((node) => ({
        id: text(node.id),
        label: text(node.label, 120),
        kind: text(node.kind, 64),
        parent: node.parent ? text(node.parent) : null,
        status: node.status,
        ...contractApi.contractPayload(node),
      }))
      .sort((left, right) => left.id.localeCompare(right.id));
    const designNodeIds = new Set(designNodes.map((node) => node.id));
    const designEdges = allEdges
      .filter((edge) => DESIGN_STATUSES.has(edge.status))
      .map((edge) => ({
        source: text(edge.source),
        target: text(edge.target),
        kind: text(edge.kind, 64),
        label: text(edge.label, 200),
        status: edge.status,
        properties: cloneJson(edge.properties),
      }))
      .sort((left, right) => relationKey(left).localeCompare(relationKey(right)));

    const referencedIds = new Set();
    designNodes.forEach((node) => {
      if (node.parent && !designNodeIds.has(node.parent)) referencedIds.add(node.parent);
    });
    designEdges.forEach((edge) => {
      if (!designNodeIds.has(edge.source)) referencedIds.add(edge.source);
      if (!designNodeIds.has(edge.target)) referencedIds.add(edge.target);
    });
    const nodeById = new Map(allNodes.map((node) => [text(node.id), node]));
    const observedEndpoints = [...referencedIds]
      .map((nodeId) => nodeById.get(nodeId))
      .filter((node) => node && !DESIGN_STATUSES.has(node.status))
      .map((node) => ({
        id: text(node.id),
        label: text(node.label, 120),
        kind: text(node.kind, 64),
        source: text(node.source || node.target_path),
      }))
      .sort((left, right) => left.id.localeCompare(right.id));

    return { nodes: designNodes, edges: designEdges, observed_endpoints: observedEndpoints };
  }

  function relationKey(edge) {
    return [edge.source, edge.target, edge.kind, edge.label].join("\u0000");
  }

  function install(graphProvider) {
    if (typeof document === "undefined") return;
    const dialog = document.querySelector("#scenario-dialog");
    const openButton = document.querySelector("#open-scenarios");
    const closeButton = document.querySelector("#scenario-close");
    const form = document.querySelector("#scenario-capture-form");
    const nameInput = document.querySelector("#scenario-name");
    const descriptionInput = document.querySelector("#scenario-description");
    const captureButton = document.querySelector("#scenario-capture");
    const leftSelect = document.querySelector("#scenario-left");
    const rightSelect = document.querySelector("#scenario-right");
    const compareButton = document.querySelector("#scenario-compare");
    const status = document.querySelector("#scenario-status");
    const draftMeta = document.querySelector("#scenario-draft-meta");
    const result = document.querySelector("#scenario-result");
    if (!dialog || !openButton || typeof graphProvider !== "function") return;

    async function refreshScenarios(preferredRightId = "") {
      const response = await fetchJson("/api/scenarios");
      const scenarios = response.scenarios || [];
      const previousLeft = leftSelect.value;
      const previousRight = preferredRightId || rightSelect.value;
      fillScenarioSelect(leftSelect, scenarios);
      fillScenarioSelect(rightSelect, scenarios);
      const ids = new Set(scenarios.map((scenario) => scenario.id));
      leftSelect.value = ids.has(previousLeft)
        ? previousLeft
        : scenarios.at(-2)?.id || scenarios[0]?.id || "";
      rightSelect.value = ids.has(previousRight)
        ? previousRight
        : scenarios.at(-1)?.id || "";
      updateCompareAvailability();
      return scenarios;
    }

    function updateCompareAvailability() {
      compareButton.disabled = !leftSelect.value
        || !rightSelect.value
        || leftSelect.value === rightSelect.value;
    }

    async function openWorkspace() {
      const snapshot = draftSnapshot(graphProvider());
      draftMeta.textContent = `${snapshot.nodes.length} design nodes · ${snapshot.edges.length} design relations · ${snapshot.observed_endpoints.length} code anchors`;
      status.textContent = "Loading saved scenarios...";
      result.hidden = true;
      dialog.showModal();
      try {
        const scenarios = await refreshScenarios();
        status.textContent = scenarios.length
          ? `${scenarios.length} saved scenario${scenarios.length === 1 ? "" : "s"}.`
          : "No scenarios saved for this project yet.";
      } catch (error) {
        status.textContent = error.message || "Could not load scenarios.";
      }
      nameInput.focus();
    }

    openButton.addEventListener("click", openWorkspace);
    closeButton.addEventListener("click", () => dialog.close());
    leftSelect.addEventListener("change", updateCompareAvailability);
    rightSelect.addEventListener("change", updateCompareAvailability);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      captureButton.disabled = true;
      status.textContent = "Capturing immutable snapshot...";
      try {
        const scenario = await fetchJson("/api/scenarios", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: nameInput.value,
            description: descriptionInput.value,
            snapshot: draftSnapshot(graphProvider()),
          }),
        });
        await refreshScenarios(scenario.id);
        nameInput.value = "";
        descriptionInput.value = "";
        status.textContent = `Captured “${scenario.name}”. The active draft was not changed.`;
      } catch (error) {
        status.textContent = error.message || "Could not capture the scenario.";
      } finally {
        captureButton.disabled = false;
      }
    });

    compareButton.addEventListener("click", async () => {
      compareButton.disabled = true;
      status.textContent = "Comparing contract drift and current-code impact...";
      try {
        const comparison = await fetchJson("/api/scenarios/compare", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ left_id: leftSelect.value, right_id: rightSelect.value }),
        });
        renderComparison(result, comparison);
        result.hidden = false;
        status.textContent = `${comparison.left.name} → ${comparison.right.name}. The active draft was not changed.`;
      } catch (error) {
        result.hidden = true;
        status.textContent = error.message || "Could not compare the scenarios.";
      } finally {
        updateCompareAvailability();
      }
    });
  }

  async function fetchJson(path, options) {
    const response = await fetch(path, options);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
    return payload;
  }

  function fillScenarioSelect(select, scenarios) {
    select.replaceChildren();
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = scenarios.length ? "Select a scenario" : "No saved scenarios";
    select.append(placeholder);
    scenarios.forEach((scenario) => {
      const option = document.createElement("option");
      option.value = scenario.id;
      option.textContent = `${scenario.name} · ${scenario.node_count} nodes · ${formatDate(scenario.created_at)}`;
      select.append(option);
    });
  }

  function formatDate(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "unknown date" : date.toLocaleString();
  }

  function renderComparison(container, comparison) {
    container.replaceChildren();
    const heading = document.createElement("div");
    heading.className = "scenario-result-heading";
    const title = document.createElement("h3");
    title.textContent = `${comparison.left.name} → ${comparison.right.name}`;
    const note = document.createElement("p");
    note.textContent = "Exact structural and contract delta";
    heading.append(title, note);
    container.append(heading, summaryGrid(comparison.summary));

    appendChangeList(container, "Nodes added", comparison.added_nodes, (node) => `${node.label} · ${node.kind}`);
    appendChangeList(container, "Nodes removed", comparison.removed_nodes, (node) => `${node.label} · ${node.kind}`);
    appendChangeList(container, "Contract fields changed", changedNodeLines(comparison.changed_nodes));
    appendChangeList(container, "Relations added", comparison.added_relations, relationLabel);
    appendChangeList(container, "Relations removed", comparison.removed_relations, relationLabel);
    appendChangeList(container, "Relations changed", changedRelationLines(comparison.changed_relations));
    appendChangeList(container, "Acceptance added", comparison.acceptance_added, acceptanceLabel);
    appendChangeList(container, "Acceptance removed", comparison.acceptance_removed, acceptanceLabel);
    if (!container.querySelector(".scenario-change-list")) {
      const empty = document.createElement("p");
      empty.className = "scenario-no-changes";
      empty.textContent = "These scenarios have no exact contract or relationship differences.";
      container.append(empty);
    }
    renderImpact(container, comparison.impact);
  }

  function impactLines(impact = {}) {
    const anchors = Array.isArray(impact.anchors) ? impact.anchors : [];
    const dependents = Array.isArray(impact.dependents) ? impact.dependents : [];
    const unresolved = Array.isArray(impact.unresolved) ? impact.unresolved : [];
    const reasonLabel = {
      no_observed_anchor: "no observed anchor",
      stale_observed_anchor: "stale observed anchor",
    };
    return {
      anchors: anchors.map((item) => {
        const contracts = Array.isArray(item.contract_node_ids) ? item.contract_node_ids.join(", ") : "unknown contract";
        return `${item.label || item.id} · ${item.kind || "unknown"} · from ${contracts}`;
      }),
      dependents: dependents.map((item) => {
        const distance = Number(item.distance) || 0;
        const hops = `${distance} hop${distance === 1 ? "" : "s"}`;
        const path = (Array.isArray(item.path) ? item.path : []).map((edge) => (
          `${edge.source_label || edge.source} -${edge.kind}-> ${edge.target_label || edge.target}`
        )).join(" ; ");
        return `${item.label || item.id} · ${hops}${path ? ` · ${path}` : ""}`;
      }),
      unresolved: unresolved.map((item) => (
        `${item.contract_node_id} · ${reasonLabel[item.reason] || item.reason || "unresolved"}`
      )),
    };
  }

  function renderImpact(container, impact) {
    if (!impact?.summary) return;
    const section = document.createElement("section");
    section.className = "scenario-impact";
    const heading = document.createElement("div");
    heading.className = "scenario-impact-heading";
    const title = document.createElement("h3");
    title.textContent = "Change impact";
    const explanation = document.createElement("p");
    explanation.textContent = "Current code reached only through authored anchors and incoming dependencies.";
    heading.append(title, explanation);

    const metrics = document.createElement("div");
    metrics.className = "scenario-impact-metrics";
    [
      ["Code anchors", impact.summary.code_anchors],
      ["Dependents", impact.summary.dependent_code],
      ["Unresolved", impact.summary.unresolved_contract_nodes],
    ].forEach(([label, value]) => {
      const badge = document.createElement("span");
      const count = document.createElement("strong");
      count.textContent = String(value || 0);
      const caption = document.createElement("small");
      caption.textContent = label;
      badge.append(count, caption);
      metrics.append(badge);
    });
    section.append(heading, metrics);

    const lines = impactLines(impact);
    appendImpactList(section, "Direct code anchors", lines.anchors);
    appendImpactList(section, "Dependent code to review", lines.dependents);
    appendImpactList(section, "Needs an explicit anchor", lines.unresolved);
    if (!lines.anchors.length && !lines.dependents.length && !lines.unresolved.length) {
      const empty = document.createElement("p");
      empty.className = "scenario-impact-empty";
      empty.textContent = "No current-code impact is evidenced by this comparison.";
      section.append(empty);
    }
    if (impact.summary.truncated) {
      const warning = document.createElement("p");
      warning.className = "scenario-impact-warning";
      warning.textContent = "The bounded analysis found more dependent code. Refine the contract anchors before relying on this list.";
      section.append(warning);
    }
    container.append(section);
  }

  function appendImpactList(container, title, lines) {
    if (!lines.length) return;
    const group = document.createElement("div");
    group.className = "scenario-impact-list";
    const heading = document.createElement("h4");
    heading.textContent = `${title} (${lines.length})`;
    const list = document.createElement("ul");
    lines.forEach((line) => {
      const item = document.createElement("li");
      item.textContent = line;
      list.append(item);
    });
    group.append(heading, list);
    container.append(group);
  }

  function summaryGrid(summary) {
    const grid = document.createElement("div");
    grid.className = "scenario-summary-grid";
    [
      ["Added", summary.added_nodes + summary.added_relations],
      ["Removed", summary.removed_nodes + summary.removed_relations],
      ["Changed", summary.changed_nodes + summary.changed_relations],
      ["Acceptance Δ", summary.acceptance_added + summary.acceptance_removed],
    ].forEach(([label, value]) => {
      const item = document.createElement("span");
      const strong = document.createElement("strong");
      strong.textContent = String(value);
      const small = document.createElement("small");
      small.textContent = label;
      item.append(strong, small);
      grid.append(item);
    });
    return grid;
  }

  function appendChangeList(container, title, items, formatter = (item) => item) {
    if (!Array.isArray(items) || !items.length) return;
    const section = document.createElement("section");
    section.className = "scenario-change-list";
    const heading = document.createElement("h4");
    heading.textContent = `${title} (${items.length})`;
    const list = document.createElement("ul");
    items.forEach((item) => {
      const entry = document.createElement("li");
      entry.textContent = formatter(item);
      list.append(entry);
    });
    section.append(heading, list);
    container.append(section);
  }

  function changedNodeLines(nodes = []) {
    return nodes.flatMap((node) => Object.entries(node.changes).map(([field, change]) => (
      `${node.label} · ${field}: ${displayValue(change.before)} → ${displayValue(change.after)}`
    )));
  }

  function changedRelationLines(relations = []) {
    return relations.flatMap((relation) => Object.entries(relation.changes).map(([field, change]) => (
      `${relation.key.join(" · ")} · ${field}: ${displayValue(change.before)} → ${displayValue(change.after)}`
    )));
  }

  function displayValue(value) {
    if (Array.isArray(value)) return value.join(", ") || "∅";
    if (value && typeof value === "object") return JSON.stringify(value);
    return String(value ?? "∅") || "∅";
  }

  function relationLabel(edge) {
    return `${edge.source} → ${edge.target} · ${edge.label || edge.kind}`;
  }

  function acceptanceLabel(item) {
    return `${item.node_id} · ${item.criterion}`;
  }

  const api = Object.freeze({ draftSnapshot, impactLines, install, renderComparison });
  globalScope.HeroArchitectureScenarios = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis === "undefined" ? this : globalThis);
