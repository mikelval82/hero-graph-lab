# Architecture Workbench v2 specification

Status: Approved as a graph design contract
Date: 2026-08-25
Graph baseline: `56af981`
Implementation status: Incremental (`AW-003` implemented; `AW-004` specified)

## Purpose

Architecture Workbench v2 groups the five prioritized capabilities into a
coherent proposed package connected to the observed Graph Lab implementation.
The graph must explain where each capability integrates, which interface it
promises and what observable outcome would make its later implementation valid.

The proposal is deliberately a design contract. It does not create source files
or claim that the classes already exist.

## Capabilities

| Capability | Proposed module and interface | Observed integration anchors |
|---|---|---|
| Architecture scenarios and A/B comparison | `scenarios.py` / `ArchitectureScenarioService.compare` | `mission.js`, `proposal-contract.js` |
| Architectural layers and semantic zoom | `static/semantic-zoom.js` / `SemanticZoomProjector.project` | `graph-views.js`, `graph-render.js`, `graph-projection.js` |
| Contract drift and change impact | `impact.py` / `ContractImpactAnalyzer.analyze` | `proposal-contract.js`, `contract_gateway.py` |
| LLM guided walkthrough | `walkthrough.py` / `GuidedWalkthroughPlanner.plan` | `explore/service.py`, `explore.js` |
| TypeScript/JavaScript adapter | `typescript_adapter.py` / `TypeScriptGraphAdapter.extract` | `extractor.py`, `server.py` |

All modules live beneath the proposed `hero_graph_lab.architecture` package.
Each module contains one public service class and one principal method so the
graph communicates both responsibility and callable boundary without designing
the entire implementation prematurely.

## Requirements

### AW-001 - Coherent connected package

The package, five modules, five classes and five principal methods form one
containment hierarchy. Every capability module has at least one explicit
relationship to the observed file or Python module it extends or consumes.

### AW-002 - Executable contract fields

Every proposed code node has a target path, qualified name, responsibility,
docstring and at least one acceptance criterion. Principal methods additionally
have an exact signature. Requirements use identifiers `AW-003` through `AW-007`.

### AW-003 - Scenario comparison

The scenario service compares two immutable design alternatives without mutating
the current browser draft. Its result describes structural differences,
contract differences and affected acceptance criteria.

### AW-004 - Semantic zoom

The projector derives a graph projection for an explicit architectural level
while preserving stable source-node identity, selection and restore behavior.
Rendering remains a browser concern owned by the existing graph projection code.

### AW-005 - Contract drift and impact

The analyzer compares normalized baseline and candidate contracts and reports
field drift plus the directly and transitively affected graph elements. It does
not approve changes or replace HARNESS verification.

### AW-006 - Guided walkthrough

The planner produces ordered, evidence-linked graph steps for a user question.
The browser may navigate those steps, but every explanation retains the observed
or proposed node identifiers that justify it.

### AW-007 - TypeScript/JavaScript adapter

The adapter emits the existing common graph schema from supported TypeScript and
JavaScript sources. It is registered behind the current extraction boundary and
does not change Python AST behavior.

## Acceptance scenarios

| ID | Expected result |
|---|---|
| AW-A01 | Selecting the package shows its intent and all five proposed capability modules |
| AW-A02 | Selecting any class shows its docstring and principal method declaration |
| AW-A03 | Selecting any principal method shows its exact signature and acceptance criterion |
| AW-A04 | Every capability module lists the named observed file/module anchors and has no disconnected warning |
| AW-A05 | Selecting an observed JavaScript anchor opens its current repository source |
| AW-A06 | Reload preserves the complete Workbench graph and contract fields |
| AW-A07 | No proposed source file is created until a reviewed HARNESS contract authorizes implementation |

## Implementation order

1. Scenario domain and comparison because it provides the alternative model.
2. Semantic projection because it provides architectural navigation.
3. Drift and impact over normalized contracts.
4. Guided walkthrough over the stable graph/query interfaces.
5. TypeScript/JavaScript extraction as an independent adapter.

This order records priority. Each capability still requires its own reviewed
specification before source implementation.
