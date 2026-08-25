# Architectural Layers and Semantic Zoom traceability

| Requirement | Decisions | Implementation | Evidence | Status |
|---|---|---|---|---|
| SZ-001 | SZ-D001, SZ-D002, SZ-D007 | selector in `index.html`; level state in `app.js` | usability review rejected global levels | Reverted |
| SZ-002 | SZ-D003, SZ-D004, SZ-D006, SZ-D007 | `SemanticZoomProjector.project` | deterministic tests and live graph smoke | Reverted |
| SZ-003 | SZ-D004, SZ-D007 | `transitionSelection` and `setArchitectureLevel` | selection tests | Reverted |
| SZ-004 | SZ-D001, SZ-D007 | `semanticDetail` and `semanticTextVisibility` | threshold tests | Reverted |
| SZ-005 | SZ-D002, SZ-D005, SZ-D007 | tool guards and projection precedence | regressions passed but usability was not accepted | Reverted |
| SZ-006 | SZ-D001, SZ-D007 | context-bar control and responsive CSS | control added visual complexity | Reverted |
| SZ-007 | SZ-D003, SZ-D007 | pure JS module | implementation removed | Reverted |

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
| `e1ff933` | reverted the extracted-relation identity change |
| `6df1076` | reverted the selector, application and renderer integration |
| `9bca594` | removed the now-unused projector and its tests |

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

## Rejection record - 2026-08-25

- User acceptance: rejected because switching levels generated too many nodes
  and relationships to support comprehension.
- Engineering review: 424 added runtime lines duplicated much of the existing
  scoped Flow behavior for insufficient practical value.
- Process finding: the feature had not received a rendered Playwright check;
  automated and endpoint evidence did not justify declaring visual completion.
- Outcome: runtime, integration and feature tests reverted in `e1ff933`,
  `6df1076` and `9bca594`. The specification remains only for auditability.
- Post-revert regression: 40 JavaScript tests and 48 Python tests passed; the
  live index contains Flow and Focus, contains no layer selector, and the
  removed `/semantic-zoom.js` asset returns HTTP 404.
- Follow-up constraint: improve existing Flow surgically only after establishing
  a rendered baseline; do not introduce another global layer selector.
