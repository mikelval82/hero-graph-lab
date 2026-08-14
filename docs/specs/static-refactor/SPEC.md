# Static JavaScript refactor specification

Status: Structural implementation complete; Flow interaction correction verified
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

### SFR-010 — Consistent Flow interaction policy

Flow navigation shall apply the same state invariants across pointer and keyboard entry points:

- Repeated single-click selection is idempotent. The first click of a double-click sequence must not clear the selected node or its pending relationship.
- Double-clicking a previously selected related node must retain the relationship and direction used to append the next journey step.
- `E` toggles the selected node's expansion state. If the selected node is already expanded, collapse takes precedence over following a relationship.
- Collapsing a container removes its expanded descendants and truncates journey steps that point into those hidden descendants, while keeping the collapsed container selected.
- Collapse clears any pending Follow candidate; a subsequent double-click re-expands the container without appending or reversing a journey step.
- The explicit **Follow/Expand** and **Collapse** buttons retain their distinct actions.

### SFR-011 — Web-based project selection

Project changes shall not depend on a native window created by the Python server process:

- **Open project** and the mission form's **Browse** action open the same HTML dialog.
- The dialog accepts an absolute path on the machine running Graph Lab and submits it as JSON to the local server.
- The server validates that a non-empty absolute directory was provided before changing the active project.
- If a HARNESS worker is active, the existing confirmation and stop behavior remains in force.
- On success the graph reloads without restoring design state from the previous project; on failure the dialog remains open and displays the server error.

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
| UI-008 | Select a related leaf, then double-click it | Flow advances once and retains the relationship and direction. |
| UI-009 | Select a reverse-related container, then double-click it | The journey records the reverse relationship and renders a `<-` breadcrumb. |
| UI-010 | Press `E` on an expanded active node, then press it again | The first press collapses and the second re-expands the same node without adding journey steps. |
| UI-011 | Select an expanded ancestor while a descendant is active and press `E` or Collapse | The ancestor collapses, descendant journey steps are removed, and hidden descendants do not remain as journey context. |
| UI-012 | Collapse an ancestor, then double-click that still-selected ancestor | The ancestor re-expands in place; no stale Follow candidate adds or reverses a journey step. |
| UI-013 | Use **Open project** or mission **Browse** | A web dialog opens without invoking an operating-system folder picker. |
| UI-014 | Submit a valid absolute project path | The dialog closes and the graph/source panels reload for the selected project. |
| UI-015 | Submit an empty, relative, or missing path | The dialog remains open, shows an actionable error, and leaves the current project unchanged. |

## Delivery sequence

1. Create a tested `graph-projection.js` boundary and keep the existing command facade.
2. Extract panel layout and persistence.
3. Extract only pure graph-view transformations.
4. Reassess `mission.js` against SFR-008.
5. Run integrated validation and close the traceability matrix.

Structural extraction and behavior corrections must be separate commits whenever practical.

## Completion boundary

The structural implementation is complete when SFR-001, SFR-004, and SFR-005 have committed module boundaries and their automated checks pass. SFR-001 through SFR-007 remain only partially verified until UI-001 through UI-007 are exercised in a rendered browser. An HTTP 200 response, source inspection, and unit tests do not satisfy that visual gate.
