(() => {
  let diagramSequence = 0;
  const renderSequences = new WeakMap();
  const nodePalette = [
    { fill: "#dfeae5", stroke: "#0c5544", text: "#12372e" },
    { fill: "#f7e7bd", stroke: "#9a6b00", text: "#4b3500" },
    { fill: "#dcecf2", stroke: "#08799c", text: "#0b4254" },
    { fill: "#f7d8cf", stroke: "#b94b32", text: "#5d2418" },
    { fill: "#e3e0f0", stroke: "#65558f", text: "#32264f" },
  ];

  if (globalThis.mermaid) {
    globalThis.mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "base",
      fontFamily: "Bahnschrift, Trebuchet MS, sans-serif",
      flowchart: { htmlLabels: false },
      themeVariables: {
        primaryColor: "#dfeae5",
        primaryTextColor: "#18201d",
        primaryBorderColor: "#0c5544",
        lineColor: "#68716d",
        secondaryColor: "#f7e7bd",
        tertiaryColor: "#e2f1f6",
        clusterBkg: "#f4f5f0",
        clusterBorder: "#68716d",
        edgeLabelBackground: "#fbfcf8",
        fontFamily: "Bahnschrift, Trebuchet MS, sans-serif",
      },
    });
  }

  function safeNodeLabels(svgSource) {
    const template = document.createElement("template");
    template.innerHTML = svgSource;
    return new Map(
      [...template.content.querySelectorAll(".node")].map((node) => [
        node.id,
        [...node.querySelectorAll(".nodeLabel p")].flatMap((label) =>
          label.innerHTML.split(/<br\s*\/?\s*>/i).map((line) => {
            const text = document.createElement("span");
            text.innerHTML = globalThis.DOMPurify.sanitize(line, {
              ALLOWED_TAGS: [],
              ALLOWED_ATTR: [],
            });
            return text.textContent.trim();
          }),
        ).filter(Boolean),
      ]),
    );
  }

  function applySafeNodeLabels(container, labels) {
    const svg = container.querySelector("svg");
    const viewBox = svg?.viewBox?.baseVal;
    if (svg && viewBox?.width && viewBox?.height) {
      svg.style.width = `${Math.min(viewBox.width, 1600)}px`;
      svg.style.height = "auto";
    }
    labels.forEach((lines, nodeId) => {
      const node = svg?.querySelector(`[id="${CSS.escape(nodeId)}"]`);
      if (!node || !lines.length) return;
      const nodeIndex = [...svg.querySelectorAll(".node")].indexOf(node);
      const palette = nodePalette[nodeIndex % nodePalette.length];
      const shape = node.querySelector(".label-container, rect, polygon, path");
      const explicitStyle = shape?.getAttribute("style") || "";
      if (shape && !/(?:^|;)\s*(?:fill|stroke)\s*:/.test(explicitStyle)) {
        shape.style.fill = palette.fill;
        shape.style.stroke = palette.stroke;
        shape.style.strokeWidth = "2px";
      }
      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("class", "safe-node-label");
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("y", String(-((lines.length - 1) * 9)));
      text.style.fill = palette.text;
      lines.forEach((line, index) => {
        const span = document.createElementNS("http://www.w3.org/2000/svg", "tspan");
        span.setAttribute("x", "0");
        span.setAttribute("dy", index === 0 ? "0" : "18");
        span.textContent = line;
        text.append(span);
      });
      node.append(text);
    });
  }

  function emphasizeDirectionMarkers(container) {
    container.querySelectorAll("marker").forEach((marker) => {
      marker.setAttribute("markerWidth", String(Math.max(12, Number(marker.getAttribute("markerWidth")) || 0)));
      marker.setAttribute("markerHeight", String(Math.max(12, Number(marker.getAttribute("markerHeight")) || 0)));
    });
    container.querySelectorAll("path[marker-end]").forEach((path) => {
      path.style.strokeWidth = String(Math.max(2, Number.parseFloat(getComputedStyle(path).strokeWidth) || 0));
    });
  }

  async function render(container, source, { prefix = "rich-mermaid" } = {}) {
    const sequence = (renderSequences.get(container) || 0) + 1;
    renderSequences.set(container, sequence);
    if (!globalThis.marked || !globalThis.DOMPurify) {
      container.textContent = "Markdown preview is unavailable.";
      return;
    }
    const parsed = globalThis.marked.parse(source, { gfm: true, breaks: false });
    container.innerHTML = globalThis.DOMPurify.sanitize(parsed, { USE_PROFILES: { html: true } });
    const diagrams = [...container.querySelectorAll("pre code.language-mermaid")];
    for (const code of diagrams) {
      if (renderSequences.get(container) !== sequence) return;
      const diagram = document.createElement("div");
      diagram.className = "mermaid-diagram";
      const definition = code.textContent;
      code.parentElement.replaceWith(diagram);
      if (!globalThis.mermaid) {
        diagram.classList.add("mermaid-error");
        diagram.textContent = "Mermaid preview is unavailable.";
        continue;
      }
      try {
        const result = await globalThis.mermaid.render(`${prefix}-${++diagramSequence}`, definition);
        if (renderSequences.get(container) !== sequence) return;
        const labels = safeNodeLabels(result.svg);
        diagram.innerHTML = globalThis.DOMPurify.sanitize(result.svg, {
          USE_PROFILES: { svg: true, svgFilters: true },
        });
        applySafeNodeLabels(diagram, labels);
        emphasizeDirectionMarkers(diagram);
        result.bindFunctions?.(diagram);
      } catch (error) {
        diagram.classList.add("mermaid-error");
        diagram.textContent = `Diagram could not be rendered: ${error.message || "invalid Mermaid syntax"}`;
      }
    }
  }

  globalThis.RichContentRenderer = Object.freeze({ render });
})();
