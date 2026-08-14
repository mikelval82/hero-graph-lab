((globalScope) => {
  function copy(value) {
    return value == null ? value : structuredClone(value);
  }

  function normalizeGraph(graph) {
    return {
      nodes: graph.nodes.map((node) => ({ ...node, context: false })),
      edges: graph.edges.map((edge) => ({
        ...edge,
        id: edge.id || `projection:${edge.source}:${edge.kind}:${edge.target}`,
        memberIds: edge.memberIds || (edge.id ? [edge.id] : []),
        aggregate: Boolean(edge.aggregate || edge.memberIds?.length > 1),
      })),
    };
  }

  function mergeGraphs(current, addition) {
    const mergedNodes = new Map(current.nodes.map((node) => [node.id, node]));
    const mergedEdges = new Map(current.edges.map((edge) => [edge.id, edge]));
    const normalized = normalizeGraph(addition);
    normalized.nodes.forEach((node) => mergedNodes.set(node.id, node));
    normalized.edges.forEach((edge) => mergedEdges.set(edge.id, edge));
    return { nodes: [...mergedNodes.values()], edges: [...mergedEdges.values()] };
  }

  function createProjection({ recommendation, depth, graph, activeAnchor, returnView }) {
    return {
      type: recommendation.type,
      label: recommendation.label,
      view: recommendation.view,
      options: copy(recommendation.options),
      depth,
      graph: normalizeGraph(graph),
      history: [],
      activeAnchor,
      savedLayout: null,
      returnView: copy(returnView),
    };
  }

  function replaceDepth(projection, { depth, graph, activeAnchor }) {
    return {
      ...projection,
      depth,
      graph: normalizeGraph(graph),
      history: [],
      activeAnchor,
      savedLayout: null,
    };
  }

  function expandState(projection, { anchorId, addition, viewState }) {
    const graph = mergeGraphs(projection.graph, addition);
    const changed = graph.nodes.length !== projection.graph.nodes.length
      || graph.edges.length !== projection.graph.edges.length;
    if (!changed) return { changed: false, projection };
    const historyEntry = {
      graph: copy(projection.graph),
      currentLayout: copy(viewState.currentLayout),
      graphZoom: viewState.graphZoom,
      scrollLeft: viewState.scrollLeft,
      scrollTop: viewState.scrollTop,
      selected: projection.activeAnchor,
    };
    return {
      changed: true,
      projection: {
        ...projection,
        graph,
        history: [...projection.history, historyEntry],
        activeAnchor: anchorId,
        savedLayout: null,
      },
    };
  }

  function backState(projection) {
    if (!projection.history.length) return { kind: "restore", projection };
    const previous = copy(projection.history.at(-1));
    return {
      kind: "back",
      previous,
      projection: {
        ...projection,
        graph: previous.graph,
        history: projection.history.slice(0, -1),
        activeAnchor: previous.selected,
        savedLayout: copy(previous.currentLayout),
      },
    };
  }

  const modelApi = Object.freeze({
    backState,
    createProjection,
    expandState,
    mergeGraphs,
    normalizeGraph,
    replaceDepth,
  });

  function installBrowserController() {
    const projectionDialog = document.querySelector("#projection-dialog");
    const projectionForm = document.querySelector("#projection-form");
    const createDepthSelect = document.querySelector("#projection-depth");
    const createButton = document.querySelector("#projection-open");
    const createStatus = document.querySelector("#projection-status");
    const diagramDepthSelect = document.querySelector("#diagram-depth");
    const projectionDepthSelect = document.querySelector("#graph-projection-depth");
    let pendingProjection = null;

    function selectedNode() {
      return state.graph?.nodes.find((node) => node.id === state.selected) || null;
    }

    function activeNodes() {
      return state.graph.nodes.filter((node) => node.status !== "removed");
    }

    function activeEdges() {
      return state.graph.edges.filter((edge) => edge.status !== "removed");
    }

    function definition(type) {
      return globalScope.HeroDiagrams.definitions.find((item) => item.id === type);
    }

    function captureInteractiveView() {
      return {
        view: state.view,
        positions: copy(state.positions),
        currentLayout: copy(state.currentLayout),
        viewStates: copy(state.viewStates),
        graphZoom: state.graphZoom,
        scrollLeft: graphViewport.scrollLeft,
        scrollTop: graphViewport.scrollTop,
        selected: state.selected,
        selectedRelation: state.selectedRelation,
        layoutLocked: state.layoutLocked,
        layoutSnapshot: copy(state.layoutSnapshot),
      };
    }

    function setProjectionView(view, label) {
      state.view = view;
      document.querySelectorAll("[data-graph-view]").forEach((button) => {
        button.setAttribute("aria-pressed", String(button.dataset.graphView === view));
      });
      document.querySelector("#graph-view-label").textContent = `${label} / ${view === "focus" ? "Focus" : "Flow"}`;
    }

    function renderProjectionBar() {
      const bar = document.querySelector("#graph-projection-bar");
      const projection = state.graphProjection;
      bar.hidden = !projection;
      if (!projection) return;
      document.querySelector("#graph-projection-title").textContent = projection.label;
      document.querySelector("#graph-projection-meta").textContent = `${projection.graph.nodes.length} nodes / depth ${projection.depth} / ${projection.history.length + 1} step${projection.history.length ? "s" : ""}`;
      projectionDepthSelect.value = String(projection.depth);
      document.querySelector("#graph-projection-back").disabled = !projection.history.length;
    }

    function recommendedProjection() {
      const current = selectedNode();
      if (!current && exploreState.pinnedNodeIds.size >= 2) {
        const [fromId, toId] = [...exploreState.pinnedNodeIds];
        return { type: "path", view: "focus", label: "Pinned path", options: { fromId, toId } };
      }
      if (!current) throw new Error("Select a node or pin two nodes to create a graph projection.");
      if (current.kind === "package") return { type: "hierarchy", view: "flow", label: "Package hierarchy", options: { anchorId: current.id } };
      if (current.kind === "module") return { type: "neighborhood", view: "flow", label: "Module neighborhood", options: { anchorId: current.id } };
      if (current.kind === "class") return { type: "classes", view: "focus", label: "Class collaborators", options: { anchorId: current.id } };
      if (["function", "method"].includes(current.kind)) return { type: "calls", view: "flow", label: "Call graph", options: { anchorId: current.id } };
      return { type: "neighborhood", view: "focus", label: "Selection neighborhood", options: { anchorId: current.id } };
    }

    function activateProjection(recommendation) {
      if (state.callTrace) clearCallTrace();
      const depth = Number(diagramDepthSelect.value);
      const result = definition(recommendation.type).generate(depth, recommendation.options);
      state.graphProjection = createProjection({
        recommendation,
        depth,
        graph: result.graph,
        activeAnchor: state.selected,
        returnView: captureInteractiveView(),
      });
      state.positions = {};
      state.currentLayout = null;
      state.selectedRelation = null;
      releaseGraphLayout();
      setProjectionView(recommendation.view, recommendation.label);
      renderProjectionBar();
      updateGraphCount();
      updateTools();
      render();
      fitGraphToView();
      document.querySelector("#graph-command-status").textContent = `${recommendation.label} opened. Select a node and press G, E, or double-click to expand it.`;
      dispatchEvent(new CustomEvent("graph-selection-changed"));
    }

    function containmentExpansion(anchorId) {
      const anchor = state.graph.nodes.find((node) => node.id === anchorId);
      if (!anchor) throw new Error("The selected node is no longer available.");
      const childNodes = activeNodes().filter((node) => node.parent === anchorId);
      const nodeIds = new Set([anchorId, ...childNodes.map((node) => node.id)]);
      return {
        nodes: [anchor, ...childNodes],
        edges: activeEdges().filter((edge) => edge.kind === "contains" && nodeIds.has(edge.source) && nodeIds.has(edge.target)),
      };
    }

    function classAncestor(nodeId) {
      let current = graphNode(nodeId);
      while (current && current.kind !== "class") current = graphNode(current.parent);
      return current || null;
    }

    function classExpansion(anchorId) {
      const result = definition("classes").generate(state.graphProjection?.depth || 1, { anchorId });
      const root = classAncestor(anchorId);
      if (!root) return result.graph;
      const methods = activeNodes().filter((node) => node.parent === root.id && node.kind === "method");
      const nodeIds = new Set([root.id, ...methods.map((node) => node.id)]);
      const containment = activeEdges().filter((edge) => edge.kind === "contains" && nodeIds.has(edge.source) && nodeIds.has(edge.target));
      return {
        nodes: [...result.graph.nodes, ...methods],
        edges: [...result.graph.edges, ...containment],
      };
    }

    function expansionGraph(projection, anchorId) {
      if (projection.type === "hierarchy") return containmentExpansion(anchorId);
      if (projection.type === "classes") return classExpansion(anchorId);
      if (projection.type === "path") return definition("neighborhood").generate(projection.depth, { anchorId }).graph;
      return definition(projection.type).generate(projection.depth, { ...projection.options, anchorId }).graph;
    }

    function setProjectionDepth() {
      const projection = state.graphProjection;
      if (!projection) return;
      const depth = Number(projectionDepthSelect.value);
      try {
        const result = definition(projection.type).generate(depth, projection.options);
        state.graphProjection = replaceDepth(projection, {
          depth,
          graph: result.graph,
          activeAnchor: projection.options.anchorId || state.selected,
        });
        diagramDepthSelect.value = String(depth);
        state.selected = state.graphProjection.activeAnchor;
        state.positions = {};
        state.currentLayout = null;
        releaseGraphLayout();
        renderProjectionBar();
        syncTreeSelection();
        updateGraphCount();
        updateTools();
        render();
        fitGraphToView();
        document.querySelector("#graph-command-status").textContent = `${projection.label} regenerated at depth ${depth}.`;
        dispatchEvent(new CustomEvent("graph-selection-changed"));
      } catch (error) {
        projectionDepthSelect.value = String(projection.depth);
        document.querySelector("#graph-command-status").textContent = error.message || "Could not change projection depth.";
      }
    }

    function expandProjection(anchorId = state.selected) {
      const projection = state.graphProjection;
      if (!projection || !anchorId) return;
      try {
        const result = expandState(projection, {
          anchorId,
          addition: expansionGraph(projection, anchorId),
          viewState: {
            currentLayout: state.currentLayout,
            graphZoom: state.graphZoom,
            scrollLeft: graphViewport.scrollLeft,
            scrollTop: graphViewport.scrollTop,
          },
        });
        if (!result.changed) {
          document.querySelector("#graph-command-status").textContent = "This node has no additional elements for the active projection.";
          return;
        }
        state.graphProjection = result.projection;
        state.positions = {};
        state.currentLayout = null;
        releaseGraphLayout();
        renderProjectionBar();
        updateGraphCount();
        updateTools();
        render();
        fitGraphToView();
        document.querySelector("#graph-command-status").textContent = `${graphNode(anchorId)?.label || "Node"} expanded in ${projection.label}.`;
      } catch (error) {
        document.querySelector("#graph-command-status").textContent = error.message || "This node cannot be expanded in the active projection.";
      }
    }

    function restoreProjection() {
      const projection = state.graphProjection;
      if (!projection) return;
      const previous = projection.returnView;
      state.graphProjection = null;
      state.view = previous.view;
      state.positions = previous.positions;
      state.currentLayout = previous.currentLayout;
      state.viewStates = previous.viewStates;
      state.graphZoom = previous.graphZoom;
      state.selected = previous.selected;
      state.selectedRelation = previous.selectedRelation;
      state.layoutLocked = previous.layoutLocked;
      state.layoutSnapshot = previous.layoutSnapshot;
      document.querySelectorAll("[data-graph-view]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.graphView === state.view)));
      const viewLabel = state.view === "structure" ? "Hierarchy" : `${state.view[0].toUpperCase()}${state.view.slice(1)}`;
      document.querySelector("#graph-view-label").textContent = `${viewLabel} Graph`;
      updateLayoutLockControl();
      renderProjectionBar();
      syncTreeSelection();
      updateGraphCount();
      updateTools();
      render();
      requestAnimationFrame(() => {
        applyGraphScale();
        graphViewport.scrollTo({ left: previous.scrollLeft, top: previous.scrollTop });
      });
      document.querySelector("#graph-command-status").textContent = "Interactive projection closed. Previous view restored.";
      dispatchEvent(new CustomEvent("graph-selection-changed"));
    }

    function backProjection() {
      const projection = state.graphProjection;
      if (!projection) return;
      const result = backState(projection);
      if (result.kind === "restore") {
        restoreProjection();
        return;
      }
      const previous = result.previous;
      state.graphProjection = result.projection;
      state.currentLayout = previous.currentLayout;
      state.graphZoom = previous.graphZoom;
      state.selected = previous.selected;
      renderProjectionBar();
      syncTreeSelection();
      updateGraphCount();
      updateTools();
      render();
      requestAnimationFrame(() => {
        applyGraphScale();
        graphViewport.scrollTo({ left: previous.scrollLeft, top: previous.scrollTop });
      });
      document.querySelector("#graph-command-status").textContent = "Returned to the previous projection step.";
      dispatchEvent(new CustomEvent("graph-selection-changed"));
    }

    function projectSelection() {
      if (state.graphProjection) {
        expandProjection(state.selected);
        return;
      }
      try {
        pendingProjection = recommendedProjection();
        document.querySelector("#projection-kind").textContent = pendingProjection.label;
        createDepthSelect.value = diagramDepthSelect.value;
        if (!projectionDialog.open) projectionDialog.showModal();
        validateProjectionChoice();
        createDepthSelect.focus();
      } catch (error) {
        document.querySelector("#graph-command-status").textContent = error.message || "Could not create the interactive projection.";
      }
    }

    function validateProjectionChoice() {
      if (!pendingProjection) return;
      const depth = Number(createDepthSelect.value);
      try {
        const result = definition(pendingProjection.type).generate(depth, pendingProjection.options);
        createStatus.textContent = `${result.graph.nodes.length} nodes at depth ${depth}.`;
        createStatus.classList.remove("invalid");
        createButton.disabled = false;
      } catch (error) {
        createStatus.textContent = error.message || "This projection cannot be created at the selected depth.";
        createStatus.classList.add("invalid");
        createButton.disabled = true;
      }
    }

    function closeProjectionDialog() {
      pendingProjection = null;
      projectionDialog.close();
    }

    function confirmProjection(event) {
      event.preventDefault();
      if (!pendingProjection || createButton.disabled) return;
      diagramDepthSelect.value = createDepthSelect.value;
      projectionDepthSelect.value = createDepthSelect.value;
      const recommendation = pendingProjection;
      closeProjectionDialog();
      try {
        activateProjection(recommendation);
      } catch (error) {
        document.querySelector("#graph-command-status").textContent = error.message || "Could not create the interactive projection.";
      }
    }

    document.querySelector("#projection-close").addEventListener("click", closeProjectionDialog);
    document.querySelector("#projection-cancel").addEventListener("click", closeProjectionDialog);
    createDepthSelect.addEventListener("change", validateProjectionChoice);
    projectionForm.addEventListener("submit", confirmProjection);
    document.querySelector("#graph-projection-back").addEventListener("click", backProjection);
    document.querySelector("#graph-projection-restore").addEventListener("click", restoreProjection);
    projectionDepthSelect.addEventListener("change", setProjectionDepth);

    return Object.freeze({
      ...modelApi,
      backProjection,
      expandProjection,
      projectSelection,
      restoreProjection,
    });
  }

  const api = typeof document === "undefined" ? modelApi : installBrowserController();
  globalScope.HeroGraphProjection = api;
  if (typeof module !== "undefined" && module.exports) module.exports = modelApi;
})(typeof globalThis === "undefined" ? this : globalThis);
