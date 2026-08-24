# Static JavaScript refactor specification

Status: Structural implementation complete; agent proposal integrity verified; projection activation focus defect open
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
- A render caused by `E` or double-click must restore graph focus to the selected node so the next keyboard transition remains available.
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

### SFR-012 — Focus anchor and keyboard continuity

Focus is a temporary contextual view anchored to the current selection, not an independently restorable semantic selection:

- Entering Focus from Flow or Hierarchy uses the node selected in the source view. A saved Focus layout may be reused only when it belongs to that same anchor.
- Selecting another visible node in Focus immediately rebuilds the direct call neighborhood around that node and restores keyboard focus to its newly rendered SVG element.
- Focus shall not remain active without an anchor. Clearing the selection with `Esc` or a canvas click returns to the view from which Focus was entered; **Reset view** returns to a clean Flow root.
- **Expand**, **Collapse**, and `E` remain unavailable in normal Focus. Double-clicking a Focus node does not mutate Flow journey or expansion state.
- A rendered `G` Back or Restore transition restores keyboard focus to its selected node, or to the graph viewport when no node is selected, so consecutive `Esc` transitions remain available.
- Opening a `G` projection shall focus its selected rendered node, or the graph viewport when no node is selected, so the first keyboard Back/Restore command works without another pointer action.

### SFR-013 — Reviewable agent proposal drafts

Agent proposals shall remain bounded graph-design actions with an explicit persistence boundary:

- `ProposeNode` and `ProposeRelation` emit validated actions only. They do not edit source files or write browser/HARNESS state themselves.
- When the user explicitly requests graph element kinds or relationships, Propose mode preserves those requested kinds (`module` is not substituted with `package`) and stages the requested relationships when valid endpoints can be established from graph evidence.
- Once the browser accepts those actions, it persists them automatically in the existing browser-local design draft. **Save map** remains the separate explicit synchronization step to HARNESS.
- Applying a valid batch rebuilds and renders the graph immediately. For a proposed node inside the current scope, its Explorer ancestry is opened; its graph ancestry is expanded when the current view permits it.
- Selection shall not point to a proposal absent from the rendered graph. If an active Flow journey excludes the proposal, the journey is preserved and the previous rendered selection remains active; the proposal remains discoverable in Explorer.
- Removing a proposed parent removes its entire all-proposed descendant subtree, every incident relationship, and associated navigation/layout state in one operation.
- If a proposed subtree contains any non-proposed descendant, removal is refused rather than deleting extracted/modified evidence or leaving an orphan.
- These corrections remain in the existing `app.js` coordination boundary; no new module is introduced without evidence of reusable proposal-domain logic.

### SFR-014 — Semantic and responsive Flow Graph controls

The Flow Graph header shall organize commands by user intent rather than implementation history:

- navigation actions group **Trace calls**, **Expand/Follow**, and **Collapse/Back**;
- inspection actions group **Explain**, Mermaid **Diagram** (`M`), and interactive **Projection** (`G`);
- design actions group **Add node**, **Add relation**, **Edit**, and **Delete/Restore**;
- view actions group **Hide**, **Lock view**, and **Reset view**;
- draft persistence exposes its status, **Save map**, and **Discard draft** without hiding them inside the legend.

The header and graph viewport shall use content-driven layout rather than fixed vertical offsets. Tool groups may wrap as units when the resizable graph panel narrows, but individual commands must remain in their semantic group. Existing element IDs, command bindings, shortcuts, enabled states, and `M`/`G` behavior shall remain unchanged.

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
| UI-016 | Double-click an expandable node, then press `E` without another pointer action | The expanded node retains focus and collapses without adding a journey step. |
| UI-017 | Select a different node in Flow and enter Focus repeatedly | Each Focus graph is anchored to the current Flow selection, never to a prior Focus selection. |
| UI-018 | Select a visible neighbor in Focus, then immediately press a graph shortcut | Focus is restored to the rendered node and the shortcut is handled without another pointer action. |
| UI-019 | Press `Esc` in normal Focus | The view used to enter Focus is restored; an anchorless graph labelled Focus is never shown. |
| UI-020 | Use **Reset view** in Focus | The application returns to a clean, unselected Flow root. |
| UI-021 | Expand a `G` projection, then press `Esc` twice | The first press restores the preceding projection step and retains graph focus; the second restores the pre-projection view. |
| UI-022 | Double-click a node or press `E` in normal Focus | The Focus neighborhood, Flow journey, and expansion state do not change. |
| UI-023 | Apply nested module, class, and function proposals plus a relationship in a non-journey graph view | The accepted proposal batch renders immediately with `NEW` provenance, opens its Explorer ancestry, and selects the final rendered proposal. |
| UI-024 | Apply a proposal while an active Flow journey excludes it | The journey and its rendered selection remain intact; no invisible proposal becomes the active graph selection, and the proposal is available in Explorer. |
| UI-025 | Reload after accepting agent proposals | The same proposals return from the browser-local draft without any source-file change; **Save map** is still required for HARNESS synchronization. |
| UI-026 | Delete a proposed parent with only proposed descendants | The whole proposed subtree and every incident relationship disappear from state, storage, Explorer, and the rendered graph with no orphan nodes. |
| UI-027 | Try to delete a proposed parent containing a non-proposed descendant | Removal is refused with an actionable status and the graph remains unchanged. |
| UI-028 | Open `G` from a proposed node and immediately press `Esc` | The projection restores its source view without requiring a click inside the newly rendered graph. |
| UI-029 | Ask Propose mode for a module, two functions, and an existing-component relationship | The first accepted batch uses those requested node kinds and includes the explicit relationship; it does not require a corrective second prompt. |
| UI-030 | Resize the Flow Graph from a wide split to its minimum supported width | Semantic tool groups wrap without clipping, overlapping the scope bar, or covering the graph viewport. |
| UI-031 | Select nodes across Flow, Focus, and `G` projection states | Existing command labels and enabled/disabled state transitions remain correct in their new groups. |
| UI-032 | Create a local proposal draft | Draft status, **Save map**, and **Discard draft** are visible outside **Legend**; **Delete** remains visually distinct from **Hide**. |

## Delivery sequence

1. Create a tested `graph-projection.js` boundary and keep the existing command facade.
2. Extract panel layout and persistence.
3. Extract only pure graph-view transformations.
4. Reassess `mission.js` against SFR-008.
5. Run integrated validation and close the traceability matrix.

Structural extraction and behavior corrections must be separate commits whenever practical.

## Completion boundary

The structural implementation is complete when SFR-001, SFR-004, and SFR-005 have committed module boundaries and their automated checks pass. SFR-001 through SFR-007 remain only partially verified until UI-001 through UI-007 are exercised in a rendered browser. An HTTP 200 response, source inspection, and unit tests do not satisfy that visual gate.
