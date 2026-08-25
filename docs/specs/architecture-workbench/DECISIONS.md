# Architecture Workbench v2 decision log

## AW-D001 - One package with five independent capability modules

Status: Accepted
Date: 2026-08-25

The Workbench is cohesive at the product level but each capability has a separate
module and public service boundary. A single `architecture_workbench.py` would
couple comparison, projection, impact, narration and parsing without evidence
that they change together.

## AW-D002 - Keep the proposal Python-first

Status: Accepted for active Workbench proposals; `AW-004` rejected by `SZ-D007`
Date: 2026-08-25

The proposed domain services use Python interfaces, matching the current server,
HARNESS boundary and contract preview. Browser files remain explicit observed
integration anchors. The TypeScript/JavaScript adapter is itself a Python adapter
that may delegate parsing later; this avoids pretending the current preview is a
TypeScript declaration renderer.

Semantic projection was implemented as a browser-side exception and later
rejected after usability review. Its rationale, evidence and reversal remain in
`docs/specs/semantic-zoom/` rather than being erased from the design history.

## AW-D003 - Connect capabilities to exact observed files

Status: Accepted
Date: 2026-08-25

Connections target `mission.js`, `proposal-contract.js`, `graph-views.js`,
`graph-projection.js`, `explore.js` and the relevant Python modules. Package-root
containment is not accepted as implementation evidence.

## AW-D004 - One principal method per class

Status: Accepted
Date: 2026-08-25

The first design contract names the smallest interface that explains each
capability. Helper classes, repositories and additional methods will be proposed
only when Research/SPEC evidence requires them. This keeps the design useful
without turning it into speculative class scaffolding.

## AW-D005 - Relationships describe integration, not implementation

Status: Accepted
Date: 2026-08-25

`uses`, `depends_on` and labelled custom relations explain where data or behavior
crosses an existing boundary. They do not claim that the proposed module already
imports, calls or modifies the observed code.
