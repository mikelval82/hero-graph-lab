# Architecture Workbench v2 traceability

| Requirement | Decisions | Proposed nodes | Observed anchors | Status |
|---|---|---|---|---|
| AW-001 | AW-D001, AW-D003 | Package plus five module/class/method slices | All below | Specified |
| AW-002 | AW-D002, AW-D004 | All proposed nodes | Proposal contract inspector | Specified |
| AW-003 | AW-D001, AW-D005 | `scenarios.py`, `ArchitectureScenarioService.compare` | `architecture-scenarios.js`, `proposal-contract.js` | Implemented in `af429d5` and `6d95c1c` |
| AW-004 | AW-D001, AW-D003, SZ-D003, SZ-D007 | Rejected; implementation reverted | `graph-views.js`, `graph-render.js`, `graph-projection.js` | Rejected after usability review |
| AW-005 | AW-D001, AW-D005 | `impact.py`, `ContractImpactAnalyzer.analyze` | Detailed in `docs/specs/contract-impact/` | Implemented; rendered acceptance pending |
| AW-006 | AW-D001, AW-D005 | `walkthrough.py`, `GuidedWalkthroughPlanner.plan` | `explore/service.py`, `explore.js` | Specified |
| AW-007 | AW-D002, AW-D005 | `typescript_adapter.py`, `TypeScriptGraphAdapter.extract` | Detailed in `docs/specs/typescript-adapter/` | Implemented; rendered acceptance pending |

## Evidence log

- `GraphSearch` verified each JavaScript file anchor after project-source graph
  commit `56af981`.
- The original Workbench proposal was published to the browser-local draft and
  connected to observed source anchors before implementation began.
- `AW-003` implementation evidence is maintained in
  `docs/specs/architecture-scenarios/TRACEABILITY.md`.
- `AW-004` implementation, rejection and revert evidence are maintained in
  `docs/specs/semantic-zoom/TRACEABILITY.md`.
