# Static JavaScript refactor specification

Status: In progress  
Baseline: `4bcaacc`  
Scope: `src/hero_graph_lab/static`

## Problem

The browser application remains deliberately dependency-light, but three files have grown across different responsibility boundaries:

- `diagrams.js` owns both Mermaid Diagram Studio (`M`) and interactive graph projection (`G`).
- `app.js` owns application coordination, panel layout, graph navigation, code display, and graph editing.
- `mission.js` combines mission control with a design synchronization mapper.

The main risk is not file size by itself. Projection and view restoration currently span `app.js`, `diagrams.js`, and `graph-render.js`, while the existing server tests mostly assert source strings. Previous in-memory checks therefore did not establish correct rendered UI behavior.

## Goals

1. Give `M` and `G` separate implementation boundaries without changing their user-visible contract.
2. Make projection transitions and graph-view transformations testable without a browser.
3. Isolate panel layout and persistence from the application coordinator.
4. Preserve the current vanilla JavaScript deployment model and authenticated local server behavior.
5. Maintain explicit traceability from requirement to decision, code, test, and validation evidence.

## Non-goals

- Introduce React, Vue, TypeScript, a bundler, or a package-manager build step.
- Convert every script to ES modules.
- Split files solely to meet a line-count target.
- Redesign the UI or change graph semantics during structural extraction.
- Claim browser correctness from source-string or in-memory tests alone.
- Refactor `mission.js` unless the post-refactor review demonstrates immediate value.

## Requirements

### SFR-001 — Separate Diagram Studio and interactive projection

`diagrams.js` shall retain deterministic/inferred diagram generation and the `M` dialog. Interactive projection lifecycle, history, and projection UI shall live in `graph-projection.js`.

Compatibility requirements:

- `M` must not mutate the interactive graph.
- `G` must continue to be available through the existing command registry.
- Normal double-click expansion semantics must remain available.

### SFR-002 — Deterministic projection transitions

Projection behavior shall support independently testable transitions for:

- activation;
- second-node expansion;
- Back after one or more expansions;
- depth replacement;
- full Restore.

Changing hierarchy depth must replace the projected graph and clear projection history. It must not merge stale context from the previous depth.

### SFR-003 — Complete view restoration

Entering temporary graph modes shall capture and restore all relevant view state consistently:

- graph view;
- positions and current layout;
- saved per-view layouts;
- selected node and relation;
- zoom and scroll;
- layout-lock state and snapshot.

Panel collapsed/expanded state must remain independent of graph projection.

### SFR-004 — Isolated panel layout

Panel sizing, collapse state, typography, splitters, and `localStorage` persistence shall move to `panel-layout.js`. The module may request a graph reflow through an injected callback but shall not own graph navigation state.

### SFR-005 — Pure graph-view transformations

Data transformations used to build Flow, Structure, Focus, journey, and call-trace graphs shall accept explicit inputs and return new view data without reading the DOM. `app.js` shall remain the coordinator that selects which transformation to use.

### SFR-006 — Runtime compatibility

The refactor shall continue to work as directly served classic browser scripts. Reusable pure modules shall follow the existing `globalThis` plus conditional `module.exports` pattern used by `flow-navigation.js`.

### SFR-007 — Security and provenance preservation

- Mermaid rendering shall continue through `RichContentRenderer`, DOMPurify, and Mermaid strict security mode.
- The deterministic/inferred distinction shall remain explicit.
- The extractor's available relationships shall not be represented as richer evidence than the graph provides.

### SFR-008 — Conditional mission extraction

`mission.js` synchronization logic shall be extracted only if the post-`app.js` review shows active coupling, change pressure, or missing testability that justifies another boundary. Otherwise it remains unchanged and the deferral is recorded as a decision.

### SFR-009 — Validation gates

Every implementation milestone shall pass:

- `node --check` for all static scripts;
- Node unit tests for reusable pure modules;
- the full Python test suite;
- `git diff --check`;
- the applicable manual rendered-UI acceptance checks.

## Rendered-UI acceptance checks

| ID | Scenario | Expected result |
|---|---|---|
| UI-001 | Open a `G` projection | Only the projection graph is visible and edit actions are disabled. |
| UI-002 | Expand a second node | Only nodes belonging to the resulting projection are visible; no unrelated dimmed nodes remain. |
| UI-003 | Use Back after expansion | The exact preceding projection graph, selection, layout, zoom, and scroll are restored. |
| UI-004 | Change Hierarchy depth | The projection is regenerated at the selected depth and prior expansion history is cleared. |
| UI-005 | Restore view | The pre-projection view, selection, layout, zoom, and scroll return. |
| UI-006 | Inspect Explorer during the sequence | If Explorer was open, it remains visible; if intentionally collapsed, that state is preserved. |
| UI-007 | Use `M` | Diagram Studio renders without changing the interactive graph. |

## Delivery sequence

1. Create a tested `graph-projection.js` boundary and keep the existing command facade.
2. Extract panel layout and persistence.
3. Extract only pure graph-view transformations.
4. Reassess `mission.js` against SFR-008.
5. Run integrated validation and close the traceability matrix.

Structural extraction and behavior corrections must be separate commits whenever practical.
