# Architectural Layers and Semantic Zoom traceability

| Requirement | Decisions | Implementation | Evidence | Status |
|---|---|---|---|---|
| SZ-001 | SZ-D001, SZ-D002 | selector in `index.html`; level state in `app.js` | projector level test; live four-level matrix | Automated verified; rendered check pending |
| SZ-002 | SZ-D003, SZ-D004, SZ-D006 | `SemanticZoomProjector.project` | determinism, no-mutation and raw-extraction tests; live graph has zero invalid relation ids | Verified |
| SZ-003 | SZ-D004 | `transitionSelection` and `setArchitectureLevel` | exact member restore and user-replacement test | Automated verified; rendered check pending |
| SZ-004 | SZ-D001 | `semanticDetail` and `semanticTextVisibility` | threshold and progressive-text tests | Automated verified; rendered check pending |
| SZ-005 | SZ-D002, SZ-D005 | tool guards, projection precedence and Native restore | existing projection Restore regressions plus integration source assertions | Automated verified; rendered `G` check pending |
| SZ-006 | SZ-D001 | compact context-bar control and responsive CSS | live HTML delivery and server assertions | Automated verified; rendered check pending |
| SZ-007 | SZ-D003 | pure JS module; no server or HARNESS changes | Node import/tests; Python regression suite | Verified |

## Baseline evidence - 2026-08-25

- Graph Lab commit `0e4e2c2`; worktree clean.
- `graph-views.js` owns Flow, Hierarchy, Focus and call-trace derivation.
- `graph-projection.js` owns temporary `G` state and exact Restore behavior.
- `graph-render.js` renders the same kind, label and status text at every zoom.
- `app.js` stores zoom as a visual scale and does not currently expose an
  architectural level.
- The active browser-local draft may contain nodes absent from the server graph;
  therefore the current server is not an authoritative semantic-projection
  boundary.

## Implementation ledger - 2026-08-25

| Commit | Trace |
|---|---|
| `0a07145` | approved specification, decisions and initial trace matrix |
| `47e5f53` | pure deterministic projector and selection/detail tests |
| `a17a04e` | selector, application state, interaction boundaries and renderer integration |
| `8c3cb25` | stable identities for relations from the raw extraction graph |

No server endpoint, graph schema or HARNESS source file changed.

## Verification evidence - 2026-08-25

- JavaScript regression suite: 47 tests passed.
- Python regression suite: 48 tests passed.
- Live `GET /` and `GET /semantic-zoom.js`: HTTP 200; selector and projector
  markers present.
- Live extraction boundary: 368 nodes and 811 relations. Projections completed
  with zero invalid relation ids: Areas 13/21, Modules 65/111, Types 116/224,
  Members 366/808 (nodes/relations).
- The in-app Browser could not start because its trusted-path policy rejected
  the installed `browser-service.mjs`. This occurs before page navigation and is
  external to Graph Lab. Consequently, the completion boundary's interactive
  check of switching, zoom thresholds and `G` Restore remains pending; automated
  evidence is not reported as rendered-browser proof.

## Acceptance status

| Scenario | Evidence | Status |
|---|---|---|
| SZ-A01 through SZ-A05 | projector tests, including reversed input and raw relations | Passed |
| SZ-A06 | pure thresholds and renderer visibility tests | Automated passed; rendered pending |
| SZ-A07 | existing exact `G` Restore tests and app integration assertions | Automated passed; rendered pending |
| SZ-A08 | proposed/removed fixture coverage and status-preserving groups | Passed |
