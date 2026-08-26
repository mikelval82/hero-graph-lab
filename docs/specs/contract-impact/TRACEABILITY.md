# Contract Drift and Change Impact traceability

| Requirement | Decisions | Planned implementation | Evidence | Status |
|---|---|---|---|---|
| CI-001 | CI-D002 | shared pure snapshot delta and `ContractImpactAnalyzer` | Exact drift and immutability tests | Verified |
| CI-002 | CI-D003, CI-D004 | explicit anchor resolver | Positive, stale and sibling-isolation tests | Verified |
| CI-003 | CI-D003, CI-D005 | bounded incoming dependency traversal | Path, exclusion, order, duplicate-id and truncation tests | Verified |
| CI-004 | CI-D004 | nearest-module scope resolver | Nested proposal fixture and real-repository E2E | Verified |
| CI-005 | CI-D001, CI-D002, CI-D007 | enriched `/api/scenarios/compare` response | HTTP integration and isolated real-repository E2E | Verified |
| CI-006 | CI-D001 | compact renderer in scenario workspace | JavaScript formatter and delivery tests; rendered acceptance pending | In progress |
| CI-007 | CI-D006, CI-D007 | read-only advisory result | Mutation, isolated-state and regression tests | Verified |

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

## Implementation evidence - 2026-08-26

- `db27f13` records the detailed specification and decision boundary before
  implementation; `04ad809` records the red domain, HTTP and presentation
  contracts.
- `c25bdb9` adds the pure analyzer, reuses its exact snapshot delta from
  Architecture Scenarios, and enriches the existing comparison endpoint.
- `87421ad` adds the compact Change impact result to the existing scenario
  dialog without adding a graph mode, toolbar control, graph node or persisted
  state.
- Domain coverage proves exact drift, nearest-module anchoring, shortest
  incoming dependency paths, exclusion of containment/outgoing/custom edges,
  stale-anchor visibility, immutable inputs, deterministic order and explicit
  breadth/depth truncation.
- A real-repository E2E used an isolated server and state store. Changing the
  `normalizeRelation` signature produced one anchor,
  `flow-navigation.js`, and four dependents: `app.js` and its navigation test at
  one hop, then `explore.js` and `mission.js` at two hops. The result was not
  truncated and reported no unresolved contract nodes.
- That E2E exposed two duplicate node identifiers already present in the
  extracted repository graph. The analyzer now selects a stable representative
  independent of graph input order; focused coverage preserves this behavior.
- Final automated regression: `61/61` Python tests and `41/41` JavaScript tests.
  Dependency validation reports no broken requirements and `git diff --check`
  reports no whitespace errors.
- The isolated E2E server and its temporary scenarios were removed after the
  run. The main application was restarted with Gemini and its graph endpoint
  returns HTTP `200`.

## Acceptance status

| Acceptance | Evidence | Status |
|---|---|---|
| CI-A01 | Signature drift and explicit anchor fixture | Pass |
| CI-A02 | One-hop and two-hop exact path assertions | Pass |
| CI-A03 | Negative containment, outgoing and custom-edge assertions | Pass |
| CI-A04 | Shared-package sibling isolation plus real E2E | Pass |
| CI-A05 | Stale anchor returns one unresolved contract and no guessed impact | Pass |
| CI-A06 | Reversed inputs, duplicate ids and deep-copy comparisons | Pass |
| CI-A07 | HTTP comparison keeps delta and adds server-derived impact | Pass |
| CI-A08 | Formatter and static delivery pass; rendered Browser workflow | Pending |
| CI-A09 | Full Python and JavaScript suites | Pass |

## Open verification boundary

The in-app Browser still rejects its installed `browser-service.mjs` as outside
the configured trusted code path before it can navigate to Graph Lab. Therefore
no screenshot, visual spacing judgment or interactive A/B click-through is
claimed. API, domain and JavaScript results are recorded separately and do not
replace this rendered acceptance.
