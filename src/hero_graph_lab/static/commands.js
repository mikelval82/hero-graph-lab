(() => {
  const commands = new Map();
  const graphViewport = document.querySelector("#graph-viewport");
  const helpDialog = document.querySelector("#shortcut-dialog");
  const paletteDialog = document.querySelector("#command-palette-dialog");

  function selectedNode() {
    return state.graph?.nodes.find((node) => node.id === state.selected) || null;
  }

  function register(definition) {
    commands.set(definition.id, Object.freeze(definition));
  }

  function enabled(command) {
    try {
      return command.isEnabled ? Boolean(command.isEnabled()) : true;
    } catch (error) {
      return false;
    }
  }

  function execute(id) {
    const command = commands.get(id);
    if (!command || !enabled(command)) return false;
    command.execute();
    refresh();
    return true;
  }

  function refresh() {
    document.querySelectorAll("[data-command]").forEach((button) => {
      const command = commands.get(button.dataset.command);
      if (!command) return;
      const available = enabled(command);
      button.disabled = !available;
      button.setAttribute("aria-disabled", String(!available));
      if (!button.title) button.title = command.shortcut ? `${command.label} (${command.shortcut})` : command.label;
    });
    if (paletteDialog.open) renderPalette();
  }

  function setCommandStatus(message = "") {
    document.querySelector("#graph-command-status").textContent = message;
  }

  function toggleExpansion() {
    if (state.inlineExpanded.has(state.selected)) collapseSelectedNode();
    else expandSelectedNode();
  }

  function togglePin() {
    if (!state.selected) return;
    if (exploreState.pinnedNodeIds.has(state.selected)) exploreState.pinnedNodeIds.delete(state.selected);
    else exploreState.pinnedNodeIds.add(state.selected);
    updateExploreContext();
  }

  function beginRelation() {
    state.relationSource = state.selected;
    setCommandStatus(`Select a target for the relationship from ${selectedNode().label}. Press Esc to cancel.`);
    document.body.classList.add("relation-command-active");
    graphViewport.focus();
  }

  function cancelOrClear() {
    if (state.relationSource) {
      state.relationSource = null;
      document.body.classList.remove("relation-command-active");
      setCommandStatus("Relationship creation cancelled.");
      return;
    }
    if (state.callTrace) {
      toggleCallTrace();
      return;
    }
    if (state.graphProjection) {
      globalThis.HeroDiagrams.backProjection();
      return;
    }
    clearSelection();
    setCommandStatus("");
  }

  const explanationPrompt = `Explica el elemento seleccionado con evidencia del grafo y del código. Responde en español y estructura la respuesta con: responsabilidad del elemento; papel dentro del sistema; entradas, salidas y colaboradores; y una analogía útil. Incluye Mermaid únicamente si aporta claridad. Distingue hechos observados de inferencias y no propongas ni escribas cambios en archivos.`;

  register({ id: "selection.explain", label: "Explain selection", shortcut: "I", description: "Open Explore and explain the selected node", isEnabled: () => Boolean(selectedNode()) && Boolean(exploreState.sessionId) && !exploreState.pending, execute: () => submitExplorePrompt(explanationPrompt) });
  register({ id: "selection.diagram", label: "Open diagrams", shortcut: "M", description: "Choose a deterministic diagram or an inferred sequence", isEnabled: () => Boolean(state.graph), execute: () => globalThis.HeroDiagrams.open() });
  register({ id: "selection.project", label: "Project selection in graph", shortcut: "G", description: "Open or expand the contextual interactive graph projection", isEnabled: () => Boolean(state.graph && (state.selected || exploreState.pinnedNodeIds.size >= 2)), execute: () => globalThis.HeroDiagrams.projectSelection() });
  register({ id: "calls.trace", label: "Trace calls", shortcut: "T", description: "Toggle the selected function call trace", isEnabled: () => !document.querySelector("#trace-calls").disabled, execute: toggleCallTrace });
  register({ id: "view.focus", label: "Focus view", shortcut: "F", description: "Show direct callers and callees", isEnabled: () => Boolean(selectedNode()) && !state.graphProjection, execute: () => setGraphView("focus") });
  register({ id: "view.structure", label: "Hierarchy view", description: "Show containment hierarchy", isEnabled: () => !state.graphProjection, execute: () => setGraphView("structure") });
  register({ id: "view.flow", label: "Flow view", description: "Show the navigation flow", isEnabled: () => !state.graphProjection, execute: () => setGraphView("flow") });
  register({ id: "node.toggle-expansion", label: "Follow, expand, or collapse", shortcut: "E", description: "Follow a relationship or toggle children for the selected node", isEnabled: () => !document.querySelector("#expand-node").disabled || !document.querySelector("#collapse-node").disabled, execute: toggleExpansion });
  register({ id: "node.expand", label: "Follow or expand", description: "Advance Flow or reveal children", isEnabled: () => !document.querySelector("#expand-node").disabled, execute: expandSelectedNode });
  register({ id: "node.collapse", label: "Collapse", description: "Hide expanded children", isEnabled: () => !document.querySelector("#collapse-node").disabled, execute: collapseSelectedNode });
  register({ id: "selection.pin", label: "Pin context", shortcut: "P", description: "Pin or unpin the selected node in Explore", isEnabled: () => Boolean(selectedNode()), execute: togglePin });
  register({ id: "node.add", label: "Add child proposal", shortcut: "A", description: "Add a proposed child node", isEnabled: () => Boolean(state.graph) && !state.graphProjection, execute: () => openNodeDialog("add") });
  register({ id: "relation.add", label: "Add relationship", shortcut: "R", description: "Choose a target for a relationship proposal", isEnabled: () => Boolean(selectedNode()) && selectedNode().status !== "removed" && !state.graphProjection, execute: beginRelation });
  register({ id: "selection.delete", label: "Delete or restore proposal", shortcut: "Delete", description: "Toggle removal of the selected node", isEnabled: () => Boolean(selectedNode()) && !state.graphProjection, execute: removeOrRestoreSelected });
  register({ id: "selection.clear", label: "Back or restore view", shortcut: "Esc", description: "Cancel, leave call trace, step back in a projection, or clear selection", isEnabled: () => Boolean(state.relationSource || state.callTrace || state.graphProjection || state.selected || state.selectedRelation), execute: cancelOrClear });
  register({ id: "shortcuts.help", label: "Keyboard shortcuts", shortcut: "?", description: "Show keyboard shortcut help", execute: () => helpDialog.showModal() });
  register({ id: "commands.palette", label: "Command palette", shortcut: "Ctrl+K", description: "Search and run commands", execute: () => { paletteDialog.showModal(); renderPalette(); document.querySelector("#command-search").focus(); } });

  function renderHelp() {
    const list = document.querySelector("#shortcut-list");
    list.replaceChildren();
    [...commands.values()].filter((command) => command.shortcut).forEach((command) => {
      const item = document.createElement("li");
      const key = document.createElement("kbd");
      key.textContent = command.shortcut;
      const details = document.createElement("span");
      const label = document.createElement("strong");
      label.textContent = command.label;
      const description = document.createElement("small");
      description.textContent = command.description;
      details.append(label, description);
      item.append(key, details);
      list.append(item);
    });
  }

  function renderPalette() {
    const query = document.querySelector("#command-search").value.trim().toLocaleLowerCase();
    const list = document.querySelector("#command-list");
    list.replaceChildren();
    [...commands.values()].filter((command) => `${command.label} ${command.description}`.toLocaleLowerCase().includes(query)).forEach((command) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.paletteCommand = command.id;
      button.disabled = !enabled(command);
      const label = document.createElement("strong");
      label.textContent = command.label;
      const details = document.createElement("span");
      details.textContent = [command.description, command.shortcut].filter(Boolean).join(" / ");
      button.append(label, details);
      list.append(button);
    });
  }

  function editableTarget(target) {
    return target instanceof Element && Boolean(target.closest("input, textarea, select, [contenteditable='true']"));
  }

  function graphHasFocus(event) {
    return graphViewport === event.target || graphViewport.contains(event.target) || graphViewport.contains(document.activeElement);
  }

  document.addEventListener("click", (event) => {
    const commandButton = event.target.closest("[data-command]");
    if (commandButton) execute(commandButton.dataset.command);
    const paletteButton = event.target.closest("[data-palette-command]");
    if (paletteButton) {
      if (execute(paletteButton.dataset.paletteCommand)) paletteDialog.close();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (editableTarget(event.target) || document.querySelector("dialog[open]")) return;
    if (event.ctrlKey && !event.altKey && !event.shiftKey && event.key.toLocaleLowerCase() === "k") {
      event.preventDefault();
      execute("commands.palette");
      return;
    }
    if (!graphHasFocus(event) || event.ctrlKey || event.altKey || event.metaKey) return;
    const shortcuts = { i: "selection.explain", m: "selection.diagram", g: "selection.project", t: "calls.trace", f: "view.focus", e: "node.toggle-expansion", p: "selection.pin", a: "node.add", r: "relation.add", delete: "selection.delete", escape: "selection.clear", "?": "shortcuts.help" };
    const commandId = shortcuts[event.key.toLocaleLowerCase()];
    if (commandId && execute(commandId)) {
      event.preventDefault();
      if (commandId === "node.toggle-expansion") focusRenderedGraphNode();
    }
  });
  document.querySelector("#command-search").addEventListener("input", renderPalette);
  document.querySelector("#shortcut-close").addEventListener("click", () => helpDialog.close());
  document.querySelector("#command-palette-close").addEventListener("click", () => paletteDialog.close());
  addEventListener("graph-selection-changed", refresh);
  addEventListener("graph-experiment-ready", refresh);
  addEventListener("explore-state-changed", refresh);
  renderHelp();
  refresh();
  globalThis.HeroCommands = Object.freeze({ execute, refresh, definitions: commands });
})();
