# Architecture Workbench v2 traceability

| Requirement | Decisions | Proposed nodes | Observed anchors | Status |
|---|---|---|---|---|
| AW-001 | AW-D001, AW-D003 | Package plus five module/class/method slices | All below | Specified |
| AW-002 | AW-D002, AW-D004 | All proposed nodes | Proposal contract inspector | Specified |
| AW-003 | AW-D001, AW-D005 | `scenarios.py`, `ArchitectureScenarioService.compare` | `mission.js`, `proposal-contract.js` | Specified |
| AW-004 | AW-D001, AW-D003 | `semantic_zoom.py`, `SemanticZoomProjector.project` | `graph-views.js`, `graph-projection.js` | Specified |
| AW-005 | AW-D001, AW-D005 | `impact.py`, `ContractImpactAnalyzer.analyze` | `proposal-contract.js`, `contract_gateway.py` | Specified |
| AW-006 | AW-D001, AW-D005 | `walkthrough.py`, `GuidedWalkthroughPlanner.plan` | `explore/service.py`, `explore.js` | Specified |
| AW-007 | AW-D002, AW-D005 | `typescript_adapter.py`, `TypeScriptGraphAdapter.extract` | `extractor.py`, `server.py` | Specified |

## Evidence log

- `GraphSearch` verified each JavaScript file anchor after project-source graph
  commit `56af981`.
- No Workbench proposal has been emitted at this point; publication and rendered
  evidence will be appended after the MCP inbox and browser-local draft agree.
