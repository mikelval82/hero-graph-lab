# Static refactor traceability matrix

Status values: `Planned`, `In progress`, `Verified`, `Deferred`, `Blocked`.

| Requirement | Decisions | Implementation | Automated evidence | Rendered evidence | Status |
|---|---|---|---|---|---|
| SFR-001 | D-002, D-003 | `diagrams.js`, `graph-projection.js`, `index.html` | `graph-projection.test.js`; server asset-order test | UI-001, UI-007 pending | In progress |
| SFR-002 | D-003, D-004, D-006 | Pure transition API in `graph-projection.js` | Activate/expand/no-op/Back/depth tests in `graph-projection.test.js` | UI-002, UI-003, UI-004 pending | In progress |
| SFR-003 | D-004, D-006 | Projection snapshot and `restoreView` contract | Full deep snapshot restoration test | UI-003, UI-005, UI-006 pending | In progress |
| SFR-004 | D-005, D-006 | `panel-layout.js`; `HeroPanelLayout.expand` integration | `panel-layout.test.js` normalization and collapse transitions | UI-006 pending | In progress |
| SFR-005 | D-002, D-005 | `graph-views.js`; thin wrappers and coordinator in `app.js` | `graph-views.test.js` hierarchy/Flow/Focus/journey/trace tests | UI-001 through UI-005 pending | In progress |
| SFR-006 | D-002 | Classic script loading; conditional CommonJS exports in pure modules | `node --check`; server asset and order tests | Browser load pending | In progress |
| SFR-007 | D-003 | `diagrams.js`, `rich-render.js` contract preserved | Existing server assertions and Python suite | UI-007 pending | In progress |
| SFR-008 | D-007, D-008 | `mission.js` reviewed and intentionally unchanged | Post-refactor coupling and test review | Not applicable | Deferred |
| SFR-009 | D-004, D-006, D-009 | All implementation milestones | 22 Node tests, 23 Python tests, `git diff --check`, HTTP 200 | UI-001 through UI-007 remain pending; Flow checks UI-008 through UI-012 passed | In progress |
| SFR-010 | D-004, D-006, D-010, D-011, D-013, D-014 | `flow-navigation.js`, `app.js`, `commands.js` click, toggle, collapse, candidate-reset, and focus transitions | 6 focused Flow tests; 22 Node tests; 23 Python tests | UI-008 through UI-012 and UI-016 passed on 223-node graph; zero current console warnings/errors | Verified |
| SFR-011 | D-012 | Shared `project-dialog` in `index.html`; `mission.js` entry points; JSON path validation in `server.py` | Static contract plus empty/relative/missing/valid server-path tests; 22 Node and 23 Python tests | UI-013 through UI-015 pending: no browser instance available | In progress |
| SFR-012 | D-015, D-018 | `app.js` anchor/return transitions; `graph-projection.js` Back/Restore focus restoration; activation focus pending | Served Focus contracts; 22 Node tests; 23 Python tests; all static JavaScript syntax valid | UI-017 through UI-022 passed; UI-028 failed because initial `G` render left focus on `BODY` | In progress |
| SFR-013 | D-016, D-017, D-019 | `app.js` proposal integrity; corrected service/tool persistence wording; explicit-kind prompt correction pending | Focused red/green contracts; 22 Node tests; 23 Python tests; all static JavaScript syntax valid | UI-023 through UI-027 passed; UI-029 failed on the first Gemini request and passed only after a corrective prompt | In progress |
| SFR-014 | D-020 | Semantic control groups and content-driven graph panel layout in `index.html` and `styles.css` | Served markup/style contract; 22 Node tests; 41 Python tests; all static JavaScript syntax valid | UI-030 through UI-032 pending because browser control is unavailable | In progress |
| SFR-015 | D-021 | Canvas-first v2 layout profile and temporary manual focus in `panel-layout.js` | Default-layout Node test; served focus lifecycle contract; 22 Node and 8 focused Python tests | UI-033 and UI-034 pending | In progress |
| SFR-016 | D-022 | Projection-owned focus lifecycle in `graph-projection.js`; focused projection CSS; projection Fit control | Served projection/layout integration contract; 22 Node and 8 focused Python tests | UI-035 through UI-037 pending | In progress |
| SFR-017 | D-023 | Contextual/Design/overflow controls in `index.html` and `app.js`; Graphite + Emerald tokens and container-responsive controls in `styles.css` | Served UI contract; all static JavaScript syntax valid; 22 Node tests; 41 Python tests | UI-038 pending because browser control is unavailable | In progress |
| SFR-018 | D-024 | Collapsed Explorer heading exposes only its restore control in `styles.css` | Served scoped-style contract; 8 focused Python server tests | UI-039 reported failing before fix; post-fix recheck pending | In progress |
| SFR-019 | D-025 | Projected layout geometry in `graph-render.js` | 3 minimum-size tests; 25 Node tests; 41 Python tests; served asset contract | UI-040 still failed after the first correction: SVG filled the viewport but projected Focus content remained clustered | In progress |
| SFR-020 | D-026 | Projected Focus column placement in `graph-render.js` | 3 directed-column tests; full suites passed | UI-041 blocked by the grid displacement and multi-hop rendering error found in the first browser run | In progress |
| SFR-021 | D-027 | Shared grid cell for `.graph-viewport` and `.graph-projection-bar` in `styles.css` | Served CSS contract pending | UI-042 failed before fix: viewport started at x=521 on a 1536-pixel workspace | Planned |
| SFR-022 | D-028 | Total projected Focus strategy in `graph-render.js` | Direct-versus-multi-hop strategy tests pending | UI-043 failed before fix: 12 generated nodes, 4 positioned nodes, and `reading 'x'` | Planned |

## Evidence log

| Date | Commit | Evidence | Result |
|---|---|---|---|
| 2026-08-14 | `4bcaacc` | Baseline: all static scripts passed `node --check`; `tests/flow-navigation.test.js` | 4 passed |
| 2026-08-14 | `4bcaacc` | Baseline Python suite with cache disabled | 23 passed |
| 2026-08-14 | `4bcaacc` | Baseline `git diff --check` and common-secret-pattern scan before commit | Clean |
| 2026-08-14 | `8dc5df6` | SFR-001 structural extraction: JS syntax, existing Node tests, Python suite | 4 Node passed; 23 Python passed |
| 2026-08-14 | `45ac41c` | SFR-002/SFR-003 projection transition characterization | 10 Node passed; 23 Python passed |
| 2026-08-14 | `d1f1788` | SFR-004 panel layout extraction and persistence normalization | 14 Node passed; 23 Python passed |
| 2026-08-14 | `46475fd` | SFR-005 pure graph views and integrated automated QA | 20 Node passed; 23 Python passed; all JS syntax valid |
| 2026-08-14 | post-`46475fd` | Local application health check | HTTP 200 at `127.0.0.1:8765` |
| 2026-08-14 | post-`46475fd` | Rendered UI gate | Pending: browser runtime reported zero available instances |
| 2026-08-14 | pre-SFR-010 fix | Playwright Flow interaction matrix | Selected-leaf double-click lost navigation; selected reverse relation lost direction; `E` followed an expanded ancestor; Collapse retained descendant journey context |
| 2026-08-14 | `6c5d62c` | SFR-010 automated validation | 6 focused Flow tests; 22 Node tests; 23 Python tests; all static JavaScript syntax valid |
| 2026-08-14 | `6c5d62c` | Playwright UI-008 through UI-011 | Directed double-clicks preserved; `E` toggled without extra steps; Collapse pruned hidden descendant context |
| 2026-08-14 | `6c5d62c` | Playwright UI-012 and root restoration | Collapse cleared the pending candidate; double-click re-expanded in place; two Back actions restored 6/24 root view with no selection or dimming; zero console warnings/errors |
| 2026-08-14 | pre-SFR-011 change | Project-selection diagnosis | Button was wired and server was healthy, but selection depended on a Tkinter window owned by the server process |
| 2026-08-14 | `8590226` | SFR-011 implementation validation | All static JavaScript syntax valid; 22 Node tests; 23 Python tests; empty, relative, missing, and valid paths covered |
| 2026-08-14 | `29f88ad` | SFR-011 frontend contract validation | Served markup and `mission.js` assertions cover the shared dialog, `showModal`, and JSON path submission; 23 Python tests passed |
| 2026-08-14 | `8590226` | Restarted local server contract | One server instance; HTTP 200; dialog markup served; relative path returned 400; absolute fixture path returned 200 and loaded 24 graph nodes |
| 2026-08-14 | post-`8590226` | UI-013 through UI-015 rendered gate | Pending: in-app browser discovery returned no available browser instance |
| 2026-08-14 | pre-D-013 fix | Playwright UI-010 on `hero-graph-lab` | First `E` collapsed `LabState`; render moved focus to `BODY`; second `E` was ignored while journey state remained correct |
| 2026-08-14 | `59cdb2b` | D-013 automated validation | All static JavaScript syntax valid; 22 Node tests; 23 Python tests; served command contract asserts focus restoration |
| 2026-08-14 | `59cdb2b` | Playwright UI-010 on `hero-graph-lab` | Three consecutive `E` presses toggled `LabServerTest`; focus stayed on the selected node, journey stayed at three steps, method visibility changed 6/0/6/0, and the current console had zero warnings/errors |
| 2026-08-14 | pre-D-014 fix | Playwright UI-016 on `hero-graph-lab` | Double-click expanded `LabServerTest` but focus fell to `BODY`; immediate `E` was ignored until the node was clicked again |
| 2026-08-14 | `643daf8` | D-014 automated validation | All static JavaScript syntax valid; 22 Node tests; 23 Python tests; served contracts cover double-click and `E` focus restoration |
| 2026-08-14 | `643daf8` | Playwright UI-016 on `hero-graph-lab` | Double-click kept focus on `LabServerTest`; two immediate `E` presses collapsed and re-expanded it, journey stayed at three steps, method visibility changed 6/0/6, and the current console had zero warnings/errors |
| 2026-08-14 | pre-SFR-012 fix | Playwright Focus interaction matrix on `hero-graph-lab` | Re-entering Focus and `F` restored stale or null anchors; node selection, `Esc`, Reset, and projection Back lost keyboard continuity; `Esc` and Reset left an anchorless graph labelled Focus |
| 2026-08-14 | pre-SFR-012 fix | Playwright Focus stable interactions | Focus re-anchored correctly when a visible neighbor was clicked; normal `E` and double-click did not mutate journey/expansion; `G` and `M` restored graph state; zero current console warnings/errors |
| 2026-08-14 | `6b6bec3` | SFR-012 automated validation | Focus transition source contracts passed; all static JavaScript syntax valid; 22 Node tests; 23 Python tests; `git diff --check` clean |
| 2026-08-14 | `6b6bec3` | Playwright UI-017 through UI-020 on `hero-graph-lab` | Repeated Focus entries used the current Flow anchor; `F` preserved selection; neighbor selection retained keyboard focus; `Esc` restored Flow; Reset produced a clean 3/223 Flow root |
| 2026-08-14 | `6b6bec3` | Playwright UI-021 and UI-022 plus Hierarchy return | Consecutive `Esc` restored the prior `G` step and then exact Focus; normal Focus double-click/`E` were state-stable; `Esc` also restored Hierarchy; zero current console warnings/errors |
| 2026-08-14 | pre-SFR-013 fix | Playwright nested agent-proposal batch on the 223-node graph | Three nodes and one relation entered state and browser storage, but no `NEW` node rendered; the selected nested function was outside the navigation graph and Explorer; model persistence wording contradicted automatic local draft storage |
| 2026-08-14 | pre-SFR-013 fix | Playwright deletion of the proposed parent | The parent and incident edges left state, but two proposed descendants remained orphaned in state/storage and the deleted parent remained stale in the DOM until another render |
| 2026-08-14 | `205f47b` | SFR-013 automated validation | Focused service and served-source contracts changed from 2 failing to 2 passing; all static JavaScript syntax valid; 22 Node tests; 23 Python tests; `git diff --check` clean |
| 2026-08-14 | `205f47b` | Playwright UI-023 and UI-025 on `hero-graph-lab` | A nested module/class/function batch rendered all three `NEW` nodes immediately, selected the final function, opened Explorer ancestry, stored the draft locally, and restored three nodes plus one relation after reload |
| 2026-08-14 | `205f47b` | Playwright UI-024, UI-026, and UI-027 on `hero-graph-lab` | An excluding Flow journey retained its rendered selection and exposed the proposal in Explorer; subtree deletion removed state/storage/DOM orphans and relations; a mixed-status subtree was refused without mutation |
| 2026-08-14 | `205f47b` | Post-SFR-013 browser cleanup and console check | Reset restored 3/223 root Flow with zero changes and no local draft; the current page recorded zero warnings/errors |
| 2026-08-14 | post-`c4be50e` | Gemini proposal review E2E on `hero-graph-lab` | The first prompt produced a package plus two classes without explicit existing-component relations; the reviewer navigated the nodes, then deleted the whole proposal subtree cleanly and requested a bounded correction |
| 2026-08-14 | post-`c4be50e` | Gemini refined Telegram proposal E2E | Propose mode created `module telegram_integration`, functions `send_telegram_notification` and `process_telegram_command`, plus a proposed `depends_on` relation from `server.main`; reload restored all four reviewable changes from browser storage |
| 2026-08-14 | post-`c4be50e` | Rendered navigation across the Gemini proposal | Proposed nodes and relation worked through Flow directed double-click, repeated `E`, Focus/`Esc`, Hierarchy, Explorer selection, deletion, and reload; the current page recorded zero console warnings/errors |
| 2026-08-14 | post-`c4be50e` | Playwright UI-028 | `G` generated a projection containing the proposed module and functions, but focus remained on `BODY`; immediate `Esc` was ignored and pointer-driven **Restore view** was required |
| 2026-08-24 | pre-SFR-014 commit | Semantic Flow Graph control implementation | All static JavaScript syntax valid; 22 Node tests; 41 Python tests; `git diff --check` clean. Rendered UI-030 through UI-032 remain pending because the browser plugin rejected its installed service path as untrusted. |
| 2026-08-24 | pre-SFR-015/SFR-016 commit | Canvas-first layout and projection-owned focus | 22 Node tests and 8 focused Python server tests passed; `git diff --check` clean. Browser-visible layout restoration remains pending. |
| 2026-08-24 | pre-SFR-017 commit | Contextual tools and Graphite + Emerald visual system | All static JavaScript syntax valid; 22 Node tests; 41 Python tests; active server returned HTTP 200 with canvas-focus, Design-mode, and projection-Fit controls; `git diff --check` clean. UI-038 remains pending. |
| 2026-08-24 | pre-SFR-018 commit | Collapsed Explorer restore regression | User reported the restore button was clipped; source diagnosis found visible typography controls occupying the 38-pixel rail. Scoped CSS contract and 8 focused Python server tests passed; browser recheck remains pending. |
| 2026-08-24 | pre-SFR-019 commit | Viewport-aware `G` projection geometry | 3 focused renderer tests, all 25 Node tests, all 41 Python tests, JavaScript syntax, and the active server asset passed. Playwright launched Chrome but it exited before creating a page, so UI-040 remains pending. |

## Post-refactor size evidence

Physical line counts are descriptive, not success criteria:

| File | Baseline | Current | Boundary outcome |
|---|---:|---:|---|
| `app.js` | 1,850 | 1,522 | Panel ownership and pure view construction removed; proposal integrity remains in the coordination boundary. |
| `diagrams.js` | 849 | 531 | Interactive `G` lifecycle removed; Mermaid Studio retained. |
| `graph-projection.js` | — | 437 | Dedicated interactive projection controller and transition model. |
| `panel-layout.js` | — | 284 | Dedicated layout, collapse, typography, and persistence controller. |
| `graph-views.js` | — | 270 | DOM-free hierarchy, Flow, Focus, journey, and trace transformations. |
| `mission.js` | 994 | 994 | Deliberately deferred under SFR-008. |

The closure commit records the evidence produced at each milestone. A requirement reaches `Verified` only when its automated and rendered acceptance evidence is both available and linked here.
