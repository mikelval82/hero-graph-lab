# Architecture Scenarios traceability

| Requirement | Decisions | Planned implementation | Evidence | Status |
|---|---|---|---|---|
| AS-001 | AS-D001 | Browser snapshot plus server validator | Pending | Specified |
| AS-002 | AS-D002 | `ArchitectureScenarioService` JSON store | Pending | Specified |
| AS-003 | AS-D003 | `ArchitectureScenarioService.compare` | Pending | Specified |
| AS-004 | AS-D002 | `/api/scenarios` endpoints | Pending | Specified |
| AS-005 | AS-D004 | `architecture-scenarios.js` and dialog | Pending | Specified |
| AS-006 | AS-D001, AS-D003 | `HeroProposalContract.contractPayload` | Pending | Specified |
| AS-007 | AS-D005 | Read/capture/compare-only UI | Pending | Specified |

## Baseline evidence - 2026-08-25

- Graph Lab commit `36d5d2a`; worktree clean.
- Architecture Workbench v2 MCP delivery revision `26` is fully acknowledged by
  the browser.
- The active draft is stored in browser localStorage and has no alternative or
  comparison model.
- Graph Lab local server state currently persists observations only.
- No scenario API, server domain service or scenario UI exists.
