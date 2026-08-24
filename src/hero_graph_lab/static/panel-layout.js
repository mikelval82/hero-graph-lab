((globalScope) => {
  const LAYOUT_STORAGE_KEY = "hero-graph-lab-layout-v2";
  const TYPOGRAPHY_STORAGE_KEY = "hero-graph-lab-typography-v1";
  const PANELS = ["explorer", "code", "inspector"];
  const typographyDefaults = { explorer: 14, graph: 14, code: 14, inspector: 14 };
  const typographyLimits = {
    explorer: [11, 22],
    graph: [10, 22],
    code: [11, 24],
    inspector: [11, 24],
  };

  function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, value));
  }

  function defaultLayout() {
    return { explorerWidth: null, graphRatio: 65, inspectorWidth: null, collapsed: ["code"] };
  }

  function normalizeLayout(value) {
    const normalized = defaultLayout();
    if (!value || typeof value !== "object") return normalized;
    if (Number.isFinite(value.explorerWidth)) normalized.explorerWidth = value.explorerWidth;
    if (Number.isFinite(value.graphRatio)) normalized.graphRatio = clamp(value.graphRatio, 30, 70);
    if (Number.isFinite(value.inspectorWidth)) normalized.inspectorWidth = value.inspectorWidth;
    if (Array.isArray(value.collapsed)) {
      normalized.collapsed = [...new Set(value.collapsed.filter((panel) => PANELS.includes(panel)))];
    }
    return normalized;
  }

  function normalizeTypography(value) {
    const normalized = { ...typographyDefaults };
    if (!value || typeof value !== "object") return normalized;
    Object.keys(normalized).forEach((panel) => {
      if (!Number.isFinite(value[panel])) return;
      const [minimum, maximum] = typographyLimits[panel];
      normalized[panel] = clamp(value[panel], minimum, maximum);
    });
    return normalized;
  }

  function setPanelCollapsed(layout, panel, collapsed) {
    if (!PANELS.includes(panel)) return normalizeLayout(layout);
    const next = normalizeLayout(layout);
    const collapsedPanels = new Set(next.collapsed);
    if (collapsed) collapsedPanels.add(panel);
    else collapsedPanels.delete(panel);
    next.collapsed = [...collapsedPanels];
    return next;
  }

  const modelApi = Object.freeze({
    defaultLayout,
    normalizeLayout,
    normalizeTypography,
    setPanelCollapsed,
  });

  function installBrowserController() {
    const appLayout = document.querySelector("#app-layout");
    const workspace = document.querySelector("#workspace");
    let layout = defaultLayout();
    let typography = { ...typographyDefaults };

    function inspectorVisible() {
      return getComputedStyle(document.querySelector("#inspector")).display !== "none";
    }

    function explorerMaximum() {
      const inspectorSpace = inspectorVisible()
        ? (layout.inspectorWidth || document.querySelector("#inspector").getBoundingClientRect().width) + 6
        : 0;
      return Math.max(180, Math.min(480, appLayout.clientWidth - inspectorSpace - 672));
    }

    function inspectorMaximum() {
      const explorerSpace = document.querySelector("#project-panel").getBoundingClientRect().width;
      const proportionalMaximum = appLayout.clientWidth * .65;
      return Math.max(190, Math.min(proportionalMaximum, appLayout.clientWidth - explorerSpace - 486));
    }

    function apply() {
      const collapsed = new Set(layout.collapsed);
      document.body.classList.toggle("explorer-collapsed", collapsed.has("explorer"));
      document.body.classList.toggle("code-collapsed", collapsed.has("code"));
      document.body.classList.toggle("inspector-collapsed", collapsed.has("inspector"));
      document.querySelectorAll("[data-collapse-panel]").forEach((button) => {
        const panel = button.dataset.collapsePanel;
        const isCollapsed = collapsed.has(panel);
        button.setAttribute("aria-expanded", String(!isCollapsed));
        button.setAttribute("aria-label", `${isCollapsed ? "Expand" : "Collapse"} ${panel === "code" ? "Code" : panel === "inspector" ? "Inspector" : "Explorer"}`);
        button.title = button.getAttribute("aria-label");
        button.querySelector("span").textContent = isCollapsed ? (panel === "explorer" ? ">" : "<") : (panel === "explorer" ? "<" : ">");
      });
      if (layout.explorerWidth !== null) {
        const explorerWidth = clamp(layout.explorerWidth, 180, explorerMaximum());
        appLayout.style.setProperty("--explorer-width", `${explorerWidth}px`);
      }
      if (layout.inspectorWidth !== null && inspectorVisible()) {
        const inspectorWidth = clamp(layout.inspectorWidth, 190, inspectorMaximum());
        appLayout.style.setProperty("--inspector-width", `${inspectorWidth}px`);
      }
      workspace.style.setProperty("--graph-width", `${clamp(layout.graphRatio, 30, 70)}%`);
      const explorerSplitter = document.querySelector("#explorer-splitter");
      explorerSplitter.setAttribute("aria-valuemax", Math.round(explorerMaximum()));
      explorerSplitter.setAttribute("aria-valuenow", Math.round(document.querySelector("#project-panel").getBoundingClientRect().width));
      const graphWidth = document.querySelector("#graph-panel").getBoundingClientRect().width;
      const codeWidth = document.querySelector("#code-panel").getBoundingClientRect().width;
      document.querySelector("#workspace-splitter").setAttribute("aria-valuenow", Math.round(graphWidth / (graphWidth + codeWidth) * 100));
      if (inspectorVisible()) {
        const inspectorSplitter = document.querySelector("#inspector-splitter");
        inspectorSplitter.setAttribute("aria-valuemax", Math.round(inspectorMaximum()));
        inspectorSplitter.setAttribute("aria-valuenow", Math.round(document.querySelector("#inspector").getBoundingClientRect().width));
      }
    }

    function save() {
      localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(layout));
    }

    function applyTypography() {
      const selectors = {
        explorer: "#project-panel",
        graph: "#graph-panel",
        code: "#code-panel",
        inspector: "#inspector",
      };
      Object.entries(selectors).forEach(([panel, selector]) => {
        const [minimum, maximum] = typographyLimits[panel];
        const size = clamp(Number(typography[panel]), minimum, maximum);
        typography[panel] = size;
        document.querySelector(selector).style.setProperty("--panel-font-size", `${size}px`);
        const controls = document.querySelector(`[data-font-panel="${panel}"]`);
        controls.querySelector("[data-font-value]").textContent = size;
        controls.querySelector('[data-font-change="-1"]').disabled = size <= minimum;
        controls.querySelector('[data-font-change="1"]').disabled = size >= maximum;
      });
    }

    function saveTypography() {
      localStorage.setItem(TYPOGRAPHY_STORAGE_KEY, JSON.stringify(typography));
    }

    function initializeTypography() {
      try {
        typography = normalizeTypography(JSON.parse(localStorage.getItem(TYPOGRAPHY_STORAGE_KEY)));
      } catch (error) {
        localStorage.removeItem(TYPOGRAPHY_STORAGE_KEY);
        typography = normalizeTypography(null);
      }
      applyTypography();
      document.querySelectorAll("[data-font-panel]").forEach((controls) => {
        controls.addEventListener("click", (event) => {
          const button = event.target.closest("button");
          if (!button) return;
          const panel = controls.dataset.fontPanel;
          if (button.hasAttribute("data-font-reset")) typography[panel] = typographyDefaults[panel];
          else if (button.dataset.fontChange) typography[panel] += Number(button.dataset.fontChange);
          applyTypography();
          saveTypography();
          if (panel === "graph" && state.graph) {
            releaseGraphLayout();
            invalidateLayout();
            render();
          }
        });
      });
    }

    function restore() {
      try {
        layout = normalizeLayout(JSON.parse(localStorage.getItem(LAYOUT_STORAGE_KEY)));
      } catch (error) {
        localStorage.removeItem(LAYOUT_STORAGE_KEY);
        layout = defaultLayout();
      }
      apply();
    }

    function resizePanel(kind, clientX) {
      if (kind === "explorer") {
        layout.explorerWidth = clamp(clientX - appLayout.getBoundingClientRect().left, 180, explorerMaximum());
      } else if (kind === "inspector") {
        layout.inspectorWidth = clamp(appLayout.getBoundingClientRect().right - clientX, 190, inspectorMaximum());
      } else {
        const bounds = workspace.getBoundingClientRect();
        const availableWidth = bounds.width - 6;
        const graphWidth = clamp(clientX - bounds.left, 360, availableWidth - 300);
        layout.graphRatio = graphWidth / availableWidth * 100;
      }
      apply();
    }

    function setupSplitter(splitterId, kind) {
      const splitter = document.querySelector(splitterId);
      let pointerId = null;
      splitter.addEventListener("pointerdown", (event) => {
        if (event.button !== 0) return;
        event.preventDefault();
        pointerId = event.pointerId;
        splitter.setPointerCapture(pointerId);
        splitter.classList.add("dragging");
        document.body.classList.add("resizing-panels");
      });
      splitter.addEventListener("pointermove", (event) => {
        if (event.pointerId === pointerId) resizePanel(kind, event.clientX);
      });
      const stop = (event) => {
        if (event.pointerId !== pointerId) return;
        pointerId = null;
        splitter.classList.remove("dragging");
        document.body.classList.remove("resizing-panels");
        save();
      };
      splitter.addEventListener("pointerup", stop);
      splitter.addEventListener("pointercancel", stop);
      splitter.addEventListener("dblclick", () => {
        if (kind === "explorer") layout.explorerWidth = 280;
        else if (kind === "inspector") layout.inspectorWidth = 260;
        else layout.graphRatio = 50;
        apply();
        save();
      });
      splitter.addEventListener("keydown", (event) => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        const bounds = splitter.getBoundingClientRect();
        let clientX = bounds.left + bounds.width / 2;
        if (event.key === "ArrowLeft") clientX -= 16;
        if (event.key === "ArrowRight") clientX += 16;
        if (event.key === "Home") clientX = kind === "inspector" ? appLayout.getBoundingClientRect().right - 190 : kind === "explorer" ? appLayout.getBoundingClientRect().left + 180 : workspace.getBoundingClientRect().left + 360;
        if (event.key === "End") clientX = kind === "inspector" ? appLayout.getBoundingClientRect().right - inspectorMaximum() : kind === "explorer" ? appLayout.getBoundingClientRect().left + explorerMaximum() : workspace.getBoundingClientRect().right - 306;
        resizePanel(kind, clientX);
        save();
      });
    }

    function setCollapsed(panel, collapsed) {
      layout = setPanelCollapsed(layout, panel, collapsed);
      apply();
      save();
    }

    function expand(panel) {
      setCollapsed(panel, false);
    }

    function snapshot() {
      return structuredClone(layout);
    }

    function canvasFocusActive(owner = "manual") {
      const className = owner === "projection" ? "projection-focus-mode" : "canvas-focus-mode";
      return document.body.classList.contains(className);
    }

    function setCanvasFocus(owner, active) {
      const className = owner === "projection" ? "projection-focus-mode" : "canvas-focus-mode";
      document.body.classList.toggle(className, Boolean(active));
      const button = document.querySelector("#canvas-focus");
      if (button) {
        const manuallyFocused = canvasFocusActive("manual");
        button.setAttribute("aria-pressed", String(manuallyFocused));
        button.querySelector("span").textContent = manuallyFocused ? "Restore layout" : "Focus canvas";
        button.title = manuallyFocused ? "Restore supporting panels" : "Hide supporting panels";
      }
    }

    function refreshFocusedCanvas() {
      requestAnimationFrame(() => {
        updateGraphViewport();
        render();
        if (state.graph) fitGraphToView();
      });
    }

    function initialize() {
      restore();
      setupSplitter("#explorer-splitter", "explorer");
      setupSplitter("#workspace-splitter", "workspace");
      setupSplitter("#inspector-splitter", "inspector");
      document.querySelectorAll("[data-collapse-panel]").forEach((button) => {
        button.addEventListener("click", () => {
          setCollapsed(button.dataset.collapsePanel, !layout.collapsed.includes(button.dataset.collapsePanel));
          requestAnimationFrame(() => {
            updateGraphViewport();
            render();
          });
        });
      });
      document.querySelector("#canvas-focus")?.addEventListener("click", () => {
        setCanvasFocus("manual", !canvasFocusActive("manual"));
        refreshFocusedCanvas();
      });
      initializeTypography();
      addEventListener("resize", () => requestAnimationFrame(() => {
        apply();
        updateGraphViewport();
        render();
      }));
    }

    initialize();
    return Object.freeze({ ...modelApi, apply, canvasFocusActive, expand, save, setCanvasFocus, snapshot });
  }

  const api = typeof document === "undefined" ? modelApi : installBrowserController();
  globalScope.HeroPanelLayout = api;
  if (typeof module !== "undefined" && module.exports) module.exports = modelApi;
})(typeof globalThis === "undefined" ? this : globalThis);
