((globalScope) => {
  const CODE_KINDS = new Set(["module", "class", "function", "method"]);
  const CALLABLE_KINDS = new Set(["function", "method"]);
  const DOCUMENTED_KINDS = new Set(["class", "function", "method"]);
  const LIST_LIMIT = 50;

  function text(value, maximum = 4000) {
    return String(value ?? "").trim().slice(0, maximum);
  }

  function list(value) {
    const values = Array.isArray(value) ? value : String(value ?? "").split("\n");
    const seen = new Set();
    const normalized = [];
    values.forEach((item) => {
      const entry = text(item, 500);
      if (!entry || seen.has(entry) || normalized.length >= LIST_LIMIT) return;
      seen.add(entry);
      normalized.push(entry);
    });
    return normalized;
  }

  function targetPath(value) {
    return text(value, 500).replaceAll("\\", "/").replace(/\/{2,}/g, "/");
  }

  function validTargetPath(value) {
    if (!value || value.startsWith("/") || /^[A-Za-z]:/.test(value)) return false;
    return value.split("/").every((part) => part && part !== "." && part !== "..");
  }

  function normalizeContractNode(node = {}) {
    const description = text(node.designDescription ?? node.description, 2000);
    return {
      ...node,
      label: text(node.label, 120),
      target_path: targetPath(node.target_path),
      qualified_name: text(node.qualified_name, 500),
      signature: text(node.signature, 1000),
      docstring: text(node.docstring, 2000),
      designDescription: description,
      description,
      satisfies: list(node.satisfies),
      acceptance: list(node.acceptance),
    };
  }

  function contractPayload(node = {}) {
    const normalized = normalizeContractNode(node);
    return {
      kind: normalized.kind,
      description: normalized.designDescription,
      target_path: normalized.target_path,
      qualified_name: normalized.qualified_name,
      signature: normalized.signature,
      docstring: normalized.docstring,
      satisfies: [...normalized.satisfies],
      acceptance: [...normalized.acceptance],
    };
  }

  function nodeName(node) {
    const qualified = text(node.qualified_name);
    return (qualified ? qualified.split(".").at(-1) : text(node.label)) || "unnamed";
  }

  function callableDeclaration(node) {
    const normalized = normalizeContractNode(node);
    const signature = normalized.signature.startsWith("(")
      ? normalized.signature
      : normalized.signature ? `(${normalized.signature})` : "(...)";
    return `def ${nodeName(normalized)}${signature}:`;
  }

  function indentedDocstring(value, indentation) {
    return value ? `${indentation}"""${value}"""\n` : "";
  }

  function childDeclarations(node, graph) {
    return (graph?.nodes || [])
      .filter((candidate) => candidate.parent === node.id && CALLABLE_KINDS.has(candidate.kind) && candidate.status !== "removed")
      .map(normalizeContractNode);
  }

  function interfacePreview(node, graph = { nodes: [], edges: [] }) {
    const normalized = normalizeContractNode(node);
    if (normalized.kind === "class") {
      const lines = [`class ${nodeName(normalized)}:`];
      if (normalized.docstring) lines.push(`    """${normalized.docstring}"""`);
      const children = childDeclarations(normalized, graph);
      if (!children.length) lines.push("    ...");
      children.forEach((child) => {
        if (lines.length > 1) lines.push("");
        lines.push(`    ${callableDeclaration(child)}`);
        if (child.docstring) lines.push(`        """${child.docstring}"""`);
        lines.push("        ...");
      });
      return lines.join("\n");
    }
    if (CALLABLE_KINDS.has(normalized.kind)) {
      return [
        callableDeclaration(normalized),
        indentedDocstring(normalized.docstring, "    ").trimEnd(),
        "    ...",
      ].filter(Boolean).join("\n");
    }
    const heading = normalized.target_path ? `# ${normalized.target_path}` : `# ${normalized.kind || "proposal"}: ${normalized.label}`;
    const lines = [heading];
    const documentation = normalized.docstring || normalized.designDescription;
    if (documentation) lines.push(`"""${documentation}"""`);
    childDeclarations(normalized, graph).forEach((child) => {
      lines.push("", callableDeclaration(child));
      if (child.docstring) lines.push(`    """${child.docstring}"""`);
      lines.push("    ...");
    });
    return lines.join("\n");
  }

  function isProposed(node) {
    return node && node.status === "proposed";
  }

  function proposalComponent(nodeId, graph, nodeById) {
    const selected = nodeById.get(nodeId);
    if (!isProposed(selected)) return new Set([nodeId]);
    const component = new Set([nodeId]);
    const pending = [nodeId];
    while (pending.length) {
      const currentId = pending.pop();
      const current = nodeById.get(currentId);
      const candidates = [];
      if (current?.parent) candidates.push(current.parent);
      (graph.nodes || []).forEach((node) => {
        if (node.parent === currentId) candidates.push(node.id);
      });
      (graph.edges || []).forEach((edge) => {
        if (edge.status === "removed") return;
        if (edge.source === currentId) candidates.push(edge.target);
        if (edge.target === currentId) candidates.push(edge.source);
      });
      candidates.forEach((candidateId) => {
        if (component.has(candidateId) || !isProposed(nodeById.get(candidateId))) return;
        component.add(candidateId);
        pending.push(candidateId);
      });
    }
    return component;
  }

  function relationView(edge, selectedId) {
    return {
      id: edge.id,
      kind: edge.kind,
      label: text(edge.label) || edge.kind,
      source: edge.source,
      target: edge.target,
      direction: edge.source === selectedId ? "outgoing" : "incoming",
      status: edge.status || "observed",
    };
  }

  function observedImplementationNode(node, graph) {
    if (!node || node.status === "proposed" || node.status === "removed") return false;
    if (node.kind !== "package") return true;
    return node.id !== graph.root && Boolean(node.parent);
  }

  function contractConnections(nodeId, graph = { nodes: [], edges: [] }) {
    const nodeById = new Map((graph.nodes || []).map((node) => [node.id, node]));
    const selected = nodeById.get(nodeId);
    const direct = (graph.edges || [])
      .filter((edge) => edge.status !== "removed" && (edge.source === nodeId || edge.target === nodeId))
      .map((edge) => ({
        node: nodeById.get(edge.source === nodeId ? edge.target : edge.source),
        relation: relationView(edge, nodeId),
      }))
      .filter((item) => item.node);

    const structuralAncestors = [];
    let parent = selected?.parent ? nodeById.get(selected.parent) : null;
    while (parent) {
      if (!isProposed(parent)) structuralAncestors.push(parent);
      parent = parent.parent ? nodeById.get(parent.parent) : null;
    }

    const component = proposalComponent(nodeId, graph, nodeById);
    const observedAnchors = [];
    const seen = new Set();
    (graph.edges || []).forEach((edge) => {
      if (edge.status === "removed") return;
      const sourceIn = component.has(edge.source);
      const targetIn = component.has(edge.target);
      if (sourceIn === targetIn) return;
      const observedId = sourceIn ? edge.target : edge.source;
      const observed = nodeById.get(observedId);
      if (!observedImplementationNode(observed, graph)) return;
      const key = `${edge.id}|${observedId}`;
      if (seen.has(key)) return;
      seen.add(key);
      const componentId = sourceIn ? edge.source : edge.target;
      observedAnchors.push({
        node: observed,
        viaNode: nodeById.get(componentId),
        relation: relationView(edge, componentId),
      });
    });
    observedAnchors.sort((left, right) => left.node.label.localeCompare(right.node.label));
    return { direct, structuralAncestors, observedAnchors, componentNodeIds: [...component] };
  }

  function contractIssues(node, graph = { nodes: [], edges: [] }) {
    const normalized = normalizeContractNode(node);
    const issues = [];
    if (!normalized.designDescription) issues.push("Add a responsibility description.");
    if (CODE_KINDS.has(normalized.kind) && !normalized.target_path) issues.push("Add an intended target path.");
    else if (normalized.target_path && !validTargetPath(normalized.target_path)) issues.push("Use a repository-relative target path without empty, dot, or parent segments.");
    if (["class", "function", "method"].includes(normalized.kind) && !normalized.qualified_name) issues.push("Add a qualified name.");
    if (CALLABLE_KINDS.has(normalized.kind) && !normalized.signature) issues.push("Add a callable signature.");
    else if (CALLABLE_KINDS.has(normalized.kind) && !normalized.signature.startsWith("(")) issues.push("Use a callable signature beginning with `(`.");
    if (DOCUMENTED_KINDS.has(normalized.kind) && !normalized.docstring) issues.push("Add a docstring.");
    if (CODE_KINDS.has(normalized.kind) && !normalized.acceptance.length) issues.push("Add at least one acceptance criterion.");
    if (isProposed(normalized) && !contractConnections(normalized.id, graph).observedAnchors.length) {
      issues.push("No observed implementation connection.");
    }
    return issues;
  }

  const api = Object.freeze({
    contractPayload,
    contractConnections,
    contractIssues,
    interfacePreview,
    normalizeContractNode,
  });
  globalScope.HeroProposalContract = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis === "undefined" ? this : globalThis);
