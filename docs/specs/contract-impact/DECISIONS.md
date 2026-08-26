# Contract Drift and Change Impact decision log

## CI-D001 - Extend scenario comparison instead of adding a new tool mode

Status: Accepted
Date: 2026-08-26

Drift needs two immutable baselines, which Architecture Scenarios already owns.
Showing impact directly below the exact A/B delta keeps the question, evidence
and answer together. A separate toolbar control or graph mode would duplicate
selection state and consume graph space.

## CI-D002 - Keep analysis server-side and pure

Status: Accepted
Date: 2026-08-26

The server owns normalized immutable scenarios and the current extracted graph.
The browser receives a derived result and cannot submit an alternative graph.
`ContractImpactAnalyzer` has no storage and mutates no inputs, so the same domain
boundary can later serve chat or MCP without duplicating policy.

## CI-D003 - Propagate only against dependency evidence

Status: Accepted
Date: 2026-08-26

Incoming `calls`, `depends_on`, `uses` and `publishes` relationships describe a
consumer that may need review when its provider changes. Containment supplies
location, not impact, and is excluded from propagation. Output says "affected"
or "dependent", never "broken".

## CI-D004 - Use the nearest module as the contract anchor boundary

Status: Accepted
Date: 2026-08-26

Methods and classes commonly inherit the integration relationship authored on
their proposed module. Traversing farther into a shared package would connect
unrelated Workbench capabilities and recreate the visual noise rejected with
global semantic zoom.

## CI-D005 - Bound breadth and depth explicitly

Status: Accepted
Date: 2026-08-26

Three dependency hops and one hundred dependent nodes provide useful local
impact while keeping the result readable and response size predictable. The
analyzer reports truncation rather than silently presenting a bounded result as
complete.

## CI-D006 - Keep HARNESS authoritative but outside this first UI increment

Status: Accepted
Date: 2026-08-26

This increment compares saved design-contract scenarios and current observed
code. It does not query or reinterpret approved HARNESS task contracts. The
analyzer consumes the normalized contract shape shared by the design workflow,
while `contract_gateway.py` remains the execution authority boundary.

## CI-D007 - Do not persist derived impact

Status: Accepted
Date: 2026-08-26

Impact depends on the current extracted graph and may change after source edits.
Persisting it beside immutable scenarios would make stale analysis look
authoritative. It is recalculated on every comparison.

