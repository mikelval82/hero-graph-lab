# Architecture Scenarios traceability

| Requirement | Decisions | Implementation | Evidence | Status |
|---|---|---|---|---|
| AS-001 | AS-D001, AS-D006 | `draftSnapshot` and `_normalize_snapshot` | JS snapshot tests; Python immutable/invalid capture tests | Verified by automated tests |
| AS-002 | AS-D002 | `ArchitectureScenarioService` atomic JSON store | durable reload and project partition tests | Verified by automated tests |
| AS-003 | AS-D003 | `ArchitectureScenarioService.compare` | forward/reverse field, node and acceptance assertions | Verified by automated tests |
| AS-004 | AS-D002 | `/api/scenarios` endpoints | HTTP capture/list/get/compare and malformed request test | Verified by integration test |
| AS-005 | AS-D004 | `architecture-scenarios.js` and modal dialog | asset integration test and live HTTP delivery; rendered workflow blocked below | Partially verified |
| AS-006 | AS-D001, AS-D003 | `HeroProposalContract.contractPayload` plus server validation | shared-contract JS test and server validator tests | Verified by automated tests |
| AS-007 | AS-D005 | capture/compare-only module; no graph write callback | snapshot immutability and API tests | Verified by automated tests |

## Baseline evidence - 2026-08-25

- Graph Lab commit `36d5d2a`; worktree clean.
- Architecture Workbench v2 MCP delivery revision `26` is fully acknowledged by
  the browser.
- The active draft is stored in browser localStorage and has no alternative or
  comparison model.
- Graph Lab local server state currently persists observations only.
- No scenario API, server domain service or scenario UI exists.

## Implementation evidence - 2026-08-25

- `39e6693` records the specification and decision boundary before code.
- `af429d5` adds the project-scoped domain service, durable JSON persistence,
  deterministic comparison and REST boundary.
- `6d95c1c` adds the compact modal workspace, shared browser snapshot and UI
  integration tests.
- Python suite: `48 passed` using the repository virtual environment.
- JavaScript suite: `40 passed`, including navigation, projection, panel and
  proposal-contract regression tests.
- Live server smoke at `http://127.0.0.1:8765/`: index and scenario asset return
  `200`; scenario listing returns `200`; an incomplete snapshot returns `400`
  without creating a scenario.

## Acceptance status

| Acceptance | Evidence | Status |
|---|---|---|
| AS-A01 | Equivalent design snapshot unit test preserves normalized proposal contracts and only referenced observed anchors | Automated equivalent passes; real Workbench capture pending |
| AS-A02 | HTTP integration captures A/B and changes one contract field | Pass |
| AS-A03 | Comparison reports the exact changed field and added node; source draft object remains unchanged | Pass |
| AS-A04 | Reverse comparison turns additions into removals | Pass |
| AS-A05 | Service re-instantiation reads the persisted scenario document; UI list endpoint is live | Persistence passes; rendered browser reload pending |
| AS-A06 | Mutable project provider returns only the selected project's scenarios | Pass |
| AS-A07 | Invalid endpoint reference and incomplete HTTP snapshot are rejected; existing JSON remains byte-identical | Pass |

## Open verification boundary

The in-app Browser runtime failed before page selection with:

`Trusted RPC dependency must resolve within a configured trusted code path: .../browser-service.mjs`

Therefore no screenshot or interactive rendered capture/compare result is being
claimed. The feature is implemented and test-backed, but AS-005 and the
completion boundary remain open until the modal is exercised in a working
Browser connection.
