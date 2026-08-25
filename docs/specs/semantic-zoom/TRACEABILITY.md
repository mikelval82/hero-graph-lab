# Architectural Layers and Semantic Zoom traceability

| Requirement | Decisions | Planned implementation | Evidence | Status |
|---|---|---|---|---|
| SZ-001 | SZ-D001, SZ-D002 | level model and compact selector | Pending | Specified |
| SZ-002 | SZ-D003, SZ-D004 | `SemanticZoomProjector.project` | Pending | Specified |
| SZ-003 | SZ-D004 | app selection transition | Pending | Specified |
| SZ-004 | SZ-D001 | detail thresholds and graph renderer | Pending | Specified |
| SZ-005 | SZ-D002, SZ-D005 | tool/shortcut and `G` boundaries | Pending | Specified |
| SZ-006 | SZ-D001 | context-bar UI and responsive CSS | Pending | Specified |
| SZ-007 | SZ-D003 | pure JS module; no server/HARNESS changes | Pending | Specified |

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
