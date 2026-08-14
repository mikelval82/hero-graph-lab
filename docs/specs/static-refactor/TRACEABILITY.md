# Static refactor traceability matrix

Status values: `Planned`, `In progress`, `Verified`, `Deferred`, `Blocked`.

| Requirement | Decisions | Implementation | Automated evidence | Rendered evidence | Status |
|---|---|---|---|---|---|
| SFR-001 | D-002, D-003 | `diagrams.js`, `graph-projection.js`, `index.html` | `graph-projection.test.js`; server asset-order test | UI-001, UI-007 pending | In progress |
| SFR-002 | D-003, D-004, D-006 | Pure transition API in `graph-projection.js` | Activate/expand/no-op/Back/depth tests in `graph-projection.test.js` | UI-002, UI-003, UI-004 pending | In progress |
| SFR-003 | D-004, D-006 | Projection snapshot and `restoreView` contract | Full deep snapshot restoration test | UI-003, UI-005, UI-006 pending | In progress |
| SFR-004 | D-005, D-006 | `panel-layout.js`; `HeroPanelLayout.expand` integration | `panel-layout.test.js` normalization and collapse transitions | UI-006 pending | In progress |
| SFR-005 | D-002, D-005 | Planned `graph-views.js`; `app.js` coordinator | Planned pure view-construction tests | UI-001 through UI-005 | Planned |
| SFR-006 | D-002 | Classic script loading and conditional CommonJS exports | `node --check`; server static asset tests | Application load smoke | Planned |
| SFR-007 | D-003 | `diagrams.js`, `rich-render.js` unchanged contract | Existing server assertions and Python suite | UI-007 | Planned |
| SFR-008 | D-007 | `mission.js` review; implementation only if approved | Review evidence to be recorded | Not applicable unless extracted | Planned |
| SFR-009 | D-004, D-006 | All milestones | Node suite, Python suite, `git diff --check` | Applicable UI checks per milestone | In progress |

## Evidence log

| Date | Commit | Evidence | Result |
|---|---|---|---|
| 2026-08-14 | `4bcaacc` | Baseline: all static scripts passed `node --check`; `tests/flow-navigation.test.js` | 4 passed |
| 2026-08-14 | `4bcaacc` | Baseline Python suite with cache disabled | 23 passed |
| 2026-08-14 | `4bcaacc` | Baseline `git diff --check` and common-secret-pattern scan before commit | Clean |
| 2026-08-14 | `8dc5df6` | SFR-001 structural extraction: JS syntax, existing Node tests, Python suite | 4 Node passed; 23 Python passed |

The matrix is updated in the same commit that completes each milestone, so a `Verified` status always points to committed evidence.
