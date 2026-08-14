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
| SFR-009 | D-004, D-006, D-009 | All implementation milestones | 20 Node tests, 23 Python tests, `git diff --check`, HTTP 200 | UI-001 through UI-007 pending: no browser instance available | In progress |
| SFR-010 | D-004, D-006, D-010 | Flow click, toggle, and collapse transitions | Regression tests pending | UI-008 through UI-011 reproduced pre-fix | In progress |

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
