# Static refactor decision log

This log is append-only for the duration of the refactor. Superseded decisions remain visible and point to their replacement.

## D-001 — Checkpoint the pre-SDD working tree

Status: Accepted
Date: 2026-08-14  
Commit: `4bcaacc`

The refactor began from a coherent but uncommitted working tree containing the current navigation, projection, and Explore changes. The full suite passed and no common credential pattern was found in changed files. A dedicated checkpoint preserves provenance and keeps subsequent commits attributable to this SDD process.

## D-002 — Preserve the no-build browser runtime

Status: Accepted
Date: 2026-08-14

New reusable JavaScript boundaries will use the established dual browser/Node pattern: expose a small frozen API through `globalThis` and conditionally through `module.exports`. This avoids a repository-wide module migration and permits `node:test` coverage without adding a build system.

## D-003 — Treat `M` and `G` as separate products sharing graph generators

Status: Accepted  
Date: 2026-08-14

`M` remains a Mermaid/export studio. `G` remains an interactive Flow/Focus projection. They may share deterministic graph-generation functions, but projection state, Back, depth, Restore, and projection UI do not belong in the Diagram Studio controller.

## D-004 — Separate structural extraction from behavior repair

Status: Accepted  
Date: 2026-08-14

Each extraction should preserve observable behavior. If an acceptance check exposes an existing defect, first capture the intended invariant in a test and fix it in a distinct change. This keeps reviews and rollback meaningful.

## D-005 — Refactor `app.js` by cohesive seams, not by size

Status: Accepted  
Date: 2026-08-14

Only panel layout and pure graph-view transformations are approved extraction seams. Code display, dialogs, persistence, and application bootstrap remain in `app.js` unless later evidence justifies moving them.

## D-006 — Keep browser-visible validation as an explicit gate

Status: Accepted  
Date: 2026-08-14

Node tests establish state-transition correctness, and Python tests establish server integration. Neither proves selection shading, panel visibility, scroll restoration, or rendered hierarchy behavior. UI-001 through UI-007 therefore remain separate acceptance evidence.

## D-007 — Make the `mission.js` refactor conditional

Status: Accepted  
Date: 2026-08-14

The design synchronization mapper is a plausible pure boundary, but no current UI regression requires moving it. It will be extracted only after the higher-value projection and `app.js` work is complete and the SFR-008 gate is evaluated.

## D-008 — Defer the `mission.js` extraction after reevaluation

Status: Accepted
Date: 2026-08-14

After completing the projection, panel, and graph-view boundaries, `mission.js` remains 994 physical lines and contains a separable design synchronization mapper. However, the completed work introduced no new coupling to that mapper, all automated tests pass, and none of the motivating UI regressions originates there. Extracting it now would add another runtime boundary without evidence of immediate benefit. SFR-008 is therefore `Deferred`, not silently abandoned. Reconsider it when synchronization behavior changes, a mapper defect appears, or direct unit coverage becomes necessary for new design operations.

## D-009 — Leave rendered acceptance unverified when no browser is available

Status: Accepted
Date: 2026-08-14

The local server returned HTTP 200, but the configured browser-control runtime reported no available browser instances. UI-001 through UI-007 must remain pending. Automated state tests and server source assertions are recorded as useful evidence but are not promoted to rendered acceptance.

## D-010 — Repair Flow interactions at the existing navigation boundary

Status: Accepted
Date: 2026-08-14

Rendered testing exposed one shared interaction defect rather than three independent features: a repeated click can clear `flowEntryCandidate`, `E` can follow instead of collapsing an already expanded node, and Collapse can retain descendants through the journey graph.

The correction will extend the existing `flow-navigation.js` transition boundary instead of introducing another module. `app.js` remains responsible for pointer coordination, while `flow-navigation.js` owns the small deterministic click and collapse transitions. `commands.js` will make the documented toggle precedence explicit. This is the smallest boundary that permits unit coverage without adding a browser framework or build dependency.

## D-011 — Invalidate pending Follow state on Collapse

Status: Accepted
Date: 2026-08-14

Post-fix rendered validation exposed a narrower sequence: after collapsing a selected ancestor, double-clicking it could reuse the relationship captured while selecting it from a descendant. That stale candidate appended a reverse visit instead of re-expanding the existing journey step.

Collapse is therefore a navigation boundary that clears `flowEntryCandidate`. The correction is a single coordinator-state reset in `app.js`; no new abstraction is justified. UI-012 records the rendered regression check.

## D-012 — Replace the server-side folder picker with a path dialog

Status: Accepted
Date: 2026-08-14

The existing button delegates folder selection to Tkinter inside the Python server. That native window can be hidden behind VS Code or unavailable when the server has no interactive desktop, while the browser provides no visible progress near the button.

Both project entry points will use one HTML dialog and send an absolute server-local path to `/api/project/select`. A browser directory upload control is not suitable because it does not expose a reliable absolute server path and would upload file contents instead of selecting an existing checkout. The server remains authoritative for path and project validation.

## D-013 — Restore graph focus after the `E` command

Status: Accepted
Date: 2026-08-14

Rendered navigation on the 223-node `hero-graph-lab` graph showed that the first `E` correctly collapses an expanded node, but the synchronous render replaces the focused SVG element. Focus falls back to `BODY`, so the command registry rejects the immediately following `E` because the graph no longer has focus.

Focus restoration belongs to the keyboard-command boundary, not the general renderer: after a successful `node.toggle-expansion`, `commands.js` will focus the newly rendered node matching `state.selected`, with the graph viewport as a fallback. Pointer-triggered Collapse and other renders keep their existing focus behavior.

## D-014 — Share focus restoration with double-click navigation

Status: Accepted
Date: 2026-08-14

Post-D-013 validation showed the same DOM replacement before the first keyboard command: double-click expands the selected node, replaces its SVG element, and leaves focus on `BODY`. An immediate `E` is therefore ignored unless the user clicks the node again.

The small focus helper will live with the graph coordinator in `app.js` and be reused by `commands.js`. Double-click and successful `E` transitions restore the selected rendered node; the general renderer and unrelated commands remain unchanged.

## D-015 — Separate the Focus anchor from saved visual state

Status: Accepted
Date: 2026-08-14

Rendered testing on the 223-node `hero-graph-lab` graph showed one shared Focus-state defect across view switching, `F`, `Esc`, Reset, and projection Back: `viewStates` stores both visual state and selection, while a Focus render replaces the selected SVG element. Re-entering Focus therefore restored an obsolete anchor, and subsequent keyboard commands could be rejected after focus fell to `BODY`.

Focus will remain inside the existing `app.js` coordinator. The current source-view selection is authoritative when entering Focus; a saved Focus layout is reusable only for the same anchor. A small `focusReturnView` value records whether Flow or Hierarchy should be restored when Focus is cleared. Targeted Focus and projection transitions will reuse `focusRenderedGraphNode`; no new state module or general render hook is justified.

## D-016 — Treat accepted agent actions as a browser-local draft

Status: Accepted
Date: 2026-08-14
Commit: `205f47b`

The proposal tools themselves only emit validated actions, but `applyAgentGraphProposals` immediately incorporates accepted actions into the graph and `saveDesign` stores that graph in browser storage. The prior model prompt's statement that proposals are not persisted until **Save map** conflicts with this runtime behavior.

The contract will name both boundaries: automatic browser-local draft persistence after acceptance, and explicit HARNESS synchronization through **Save map**. Source files remain unchanged at both stages. This corrects the description without redesigning the existing persistence model.

## D-017 — Repair proposal integrity in the existing coordinator

Status: Accepted
Date: 2026-08-14
Commit: `205f47b`

Rendered testing exposed two coupled coordinator defects: accepted proposals changed state without a graph render, and deleting a proposed parent removed only that parent while retaining its proposed descendants as orphans. A nested proposal could also become the selected node while remaining outside the rendered navigation graph.

The correction will reuse `expandTreePath`, `inlineExpanded`, `navigationGraph`, `descendantIds`, and the existing render/persistence path in `app.js`. Proposed-subtree deletion will be atomic and will refuse a mixed-status subtree. A new module is not justified because the work coordinates existing application state and has no independent reusable domain boundary.

## D-018 — Classify the first-key failure as projection activation

Status: Accepted
Date: 2026-08-14

The Gemini E2E navigation run showed that proposed nodes participate correctly in Flow, Hierarchy, Focus, Explorer, and `G` graph generation. However, opening `G` leaves focus on `BODY`; an immediate `Esc` is ignored until a pointer action restores graph focus.

This is a projection-activation focus defect, not an agent-proposal integrity defect: the proposed node is present, selected, and rendered in the projection. The future correction belongs at the existing `G` activation/render boundary and should reuse `focusRenderedGraphNode`; no proposal-specific branch or new module is justified.

## D-019 — Reinforce explicit proposal kinds in the model contract

Status: Accepted
Date: 2026-08-14

The first Gemini E2E request explicitly asked for a module, functional elements, and relationships with existing components, but the model staged a package plus two classes and no explicit relationship. The tool schemas were valid and the second, more prescriptive prompt produced the intended structure, so the defect is in instruction fidelity rather than graph mutation.

Propose mode will explicitly require preservation of user-requested node kinds and relationships. A general natural-language validator or automatic rollback is not justified: semantic intent is broader than the bounded graph schema, and every proposal remains reviewable and reversible in the UI.

## D-020 — Replace fixed Flow Graph offsets with semantic layout

Status: Accepted
Date: 2026-08-24

The current visualization toolbar requires roughly 660 pixels before the separate design controls, while the resizable graph column supports widths down to 250 pixels. Because the header, scope bar, toolbar, projection bar, and viewport use independent fixed offsets, wrapping can overlap or clip controls instead of increasing the header's height.

The graph panel will become a small content-driven CSS grid. Existing buttons will be regrouped in the HTML without changing IDs or JavaScript command ownership. Group-level wrapping is preferred over a new component framework, icon dependency, overflow menu, or JavaScript measurement logic. This resolves the observed information architecture and sizing defect at the existing HTML/CSS boundary.

## D-021 — Make Code opt-in and canvas focus non-persistent

Status: Accepted
Date: 2026-08-24

The graph cannot be the primary surface while the default workspace permanently assigns half of its center region to Code. A new layout-storage version will default Code to collapsed while preserving Explorer and Inspector. Manual canvas focus is a temporary body state layered over the saved layout; it must not rewrite panel preferences.

## D-022 — Let `G` own a temporary focus layer

Status: Accepted
Date: 2026-08-24

Projection focus will be represented independently from manual canvas focus. `G` adds and removes only its own focus state, so closing a projection cannot unexpectedly reopen panels hidden by the user. Normal graph chrome is replaced by the projection bar for the duration of `G`, rather than accumulating another toolbar over the canvas.

## D-023 — Use progressive disclosure instead of a permanent tool matrix

Status: Accepted
Date: 2026-08-24

The semantic groups introduced by D-020 improve comprehension but consume excessive height when all commands remain visible. Normal navigation/inspection stays compact, Design becomes an explicit mode, and infrequent view/help actions move behind a conventional overflow control. A small local icon vocabulary and CSS tokens are preferred over an admin template or UI framework because Graph Lab is a no-build canvas application, not a dashboard.

## D-024 — Reserve the collapsed Explorer rail for restoration

Status: Accepted
Date: 2026-08-24

Rendered acceptance showed that Explorer's typography controls remained in the 38-pixel collapsed rail and pushed its restore button outside the clipped panel. Collapsed Explorer will expose only its panel-restore command. The rule is scoped to the Explorer heading so collapsing Explorer cannot alter action groups in Code or other panels.

## D-025 — Size projected layouts from the focused canvas

Status: Accepted
Date: 2026-08-24

Rendered acceptance showed that `G` expands the application shell but keeps the graph's normal 1000 by 680 minimum layout. **Fit** is then limited by that old aspect ratio and centers a narrow SVG inside the wide focused canvas, leaving a large unused band below the projection controls.

The renderer will derive only a projected layout's minimum width and height from the live graph viewport. Normal Flow, Focus, and Hierarchy layouts retain their existing dimensions, while content can still grow beyond the viewport when the graph requires it. A CSS offset, stretched SVG, or projection-specific renderer is not justified because the defect is the minimum layout geometry, not the shell or graph semantics.

## D-026 — Distribute projected Focus columns across the canvas

Status: Accepted
Date: 2026-08-24

Post-change rendered acceptance showed that the projected SVG now fills the canvas but a class-collaboration projection still leaves most of it empty. The Focus layout always places incoming and outgoing nodes one fixed `columnGap` to either side of the selection; increasing the SVG dimensions therefore increases the unused space instead of the diagram.

Only while `G` is active, Focus will use the available horizontal span as a directed two- or three-column diagram. If relationships exist on one side only, the selection and that side occupy opposite columns; if both exist, the selection remains central. Normal Focus keeps its established compact geometry. A force-directed renderer is not justified for this deterministic placement defect.

## D-027 — Overlay the projection bar without creating a graph column

Status: Accepted
Date: 2026-08-24

Browser measurement identified the actual left-hand loss: the projection bar is explicitly placed in row 4, column 1, while the graph viewport specifies only row 4. When the bar becomes visible, CSS Grid auto-places the viewport in an implicit second column. At 1536 pixels the bar consumed the first 521 pixels and the graph began at `x=521`.

The graph viewport will explicitly occupy row 4, column 1 so the projection bar remains an overlay in the same grid cell. Absolute positioning or JavaScript measurement is unnecessary.

## D-028 — Use Flow geometry for multi-hop Focus projections

Status: Accepted
Date: 2026-08-24

The same browser run exposed a projection with 12 class nodes but positions for only the selected class and its three direct neighbors. `focusLayout` is a total layout only for a direct neighborhood; the class generator can return additional connected hops, causing rendering to read an undefined position.

Projected Focus retains the wide two- or three-column layout from D-026 when every node is a direct neighbor. If the generated projection contains indirect nodes, it reuses the existing deterministic Flow layout so every node receives a position. Normal Focus remains unchanged.
