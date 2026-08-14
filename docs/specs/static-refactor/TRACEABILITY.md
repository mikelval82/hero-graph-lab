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
| SFR-012 | D-015 | `app.js` anchor/return transitions; `graph-projection.js` Back/Restore focus restoration | Served Focus contracts; 22 Node tests; 23 Python tests; all static JavaScript syntax valid | UI-017 through UI-022 passed on the 223-node graph; Flow and Hierarchy return paths passed; zero current console warnings/errors | Verified |

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

## Post-refactor size evidence

Physical line counts are descriptive, not success criteria:

| File | Baseline | Current | Boundary outcome |
|---|---:|---:|---|
| `app.js` | 1,850 | 1,453 | Panel ownership and pure view construction removed; coordination retained. |
| `diagrams.js` | 849 | 531 | Interactive `G` lifecycle removed; Mermaid Studio retained. |
| `graph-projection.js` | — | 437 | Dedicated interactive projection controller and transition model. |
| `panel-layout.js` | — | 284 | Dedicated layout, collapse, typography, and persistence controller. |
| `graph-views.js` | — | 270 | DOM-free hierarchy, Flow, Focus, journey, and trace transformations. |
| `mission.js` | 994 | 994 | Deliberately deferred under SFR-008. |

The closure commit records the evidence produced at each milestone. A requirement reaches `Verified` only when its automated and rendered acceptance evidence is both available and linked here.
