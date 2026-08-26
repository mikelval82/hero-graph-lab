# Contract Drift and Change Impact traceability

| Requirement | Decisions | Planned implementation | Evidence | Status |
|---|---|---|---|---|
| CI-001 | CI-D002 | shared pure snapshot delta and `ContractImpactAnalyzer` | Red domain tests | Specified |
| CI-002 | CI-D003, CI-D004 | explicit anchor resolver | Positive, stale and sibling-isolation tests | Specified |
| CI-003 | CI-D003, CI-D005 | bounded incoming dependency traversal | Path, exclusion, order and truncation tests | Specified |
| CI-004 | CI-D004 | nearest-module scope resolver | Nested proposal fixture | Specified |
| CI-005 | CI-D001, CI-D002, CI-D007 | enriched `/api/scenarios/compare` response | HTTP integration test | Specified |
| CI-006 | CI-D001 | compact renderer in scenario workspace | JavaScript formatter tests; rendered acceptance | Specified |
| CI-007 | CI-D006, CI-D007 | read-only advisory result | Mutation and regression tests | Specified |

## Baseline evidence - 2026-08-26

- Graph Lab commit `40c6884`; worktree clean.
- Architecture Scenarios already persists normalized immutable snapshots and
  reports exact node, relation and acceptance drift.
- The compare endpoint currently returns no current-code impact.
- Scenario snapshots retain explicit observed endpoint ids and sources, but not
  the complete observed graph; the server can derive that graph authoritatively.
- The observed graph currently emits `contains`, `calls` and `depends_on`.
- The in-app Browser remains blocked before navigation because its installed
  service path is rejected as untrusted. No rendered baseline is claimed.

## Red evidence - 2026-08-26

- Domain tests fail at import because
  `hero_graph_lab.architecture.impact.ContractImpactAnalyzer` does not exist.
- The focused JavaScript suite keeps its two existing snapshot tests green and
  fails the new presentation contract because `impactLines` is not exported.
- The fixtures require nearest-module anchoring, exact incoming dependency
  paths, sibling isolation, stale-anchor reporting, deterministic input order,
  immutability and explicit truncation.
