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
