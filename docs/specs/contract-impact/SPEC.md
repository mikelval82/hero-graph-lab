# Contract Drift and Change Impact specification

Status: Implemented; rendered acceptance pending
Date: 2026-08-26
Parent requirement: `AW-005`
Baseline: `40c6884`

## Purpose

When two saved architecture scenarios differ, Graph Lab must explain not only
which contract fields changed, but which observed code is plausibly exposed to
that change and why. The result is decision support before approval; it is not
an implementation authorization or a substitute for HARNESS verification.

The feature extends the existing A/B comparison workspace. It does not add a
new graph mode, create synthetic graph nodes or recolor the active graph.

## User outcome

After comparing scenario A with scenario B, the user sees three bounded groups:

1. contract drift: exact node, relation and acceptance changes;
2. code anchors: observed code connected to the changed contract by explicit
   design relationships or an exact existing target path;
3. dependent code: observed callers or module dependents reached through a
   short, inspectable evidence path.

Every affected item retains its graph node id, source location and the exact
relationship path that caused it to appear.

## Requirements

### CI-001 - Exact normalized drift

`ContractImpactAnalyzer.analyze(baseline, candidate, graph)` compares two
normalized scenario snapshots without mutating either input. Its drift result
uses the same fields and relationship identity as scenario A/B comparison.

### CI-002 - Evidence-backed code anchors

A changed contract element may anchor observed code only through one of these
authored facts:

- the contract node id is an exact current graph node id;
- a design relationship connects the changed node, or its nearest code-module
  ancestor, to an observed endpoint;
- a non-empty `target_path` exactly matches the `source` of one current observed
  file or module node.

Label similarity, package-root containment and HTML script order are not
evidence. An absent or stale anchor is reported as unresolved.

### CI-003 - Conservative dependent traversal

Starting from the code anchors, the analyzer follows incoming observed
`calls`, `depends_on`, `uses` and `publishes` relationships. It never propagates
through `contains`, proposed/removed relationships or arbitrary custom labels.

The traversal is deterministic, keeps the shortest evidence path, stops after
three relationships and returns at most one hundred dependent nodes. The result
states when that bound truncated the analysis.

### CI-004 - No sibling leakage

A changed method or class may inherit an observed anchor from its nearest
proposed module ancestor. Traversal stops at that module and must not cross a
shared Workbench package into unrelated capability modules.

### CI-005 - Existing comparison API

`POST /api/scenarios/compare` remains the single browser boundary. Its current
delta response is preserved and gains an `impact` object calculated from the
server's current extracted graph. The client cannot supply or override that
observed graph.

### CI-006 - Compact comparison presentation

The existing scenario result renders a compact Change impact section after the
exact delta. It shows counts, code anchors, dependent code with hop count and a
human-readable evidence path, plus unresolved contract elements. Long lists are
scrollable within the existing dialog.

The UI adds no toolbar button, graph projection, node, relationship or saved
state.

### CI-007 - Authority boundary

The analysis is advisory. It does not approve a proposal, mutate a scenario,
write source, claim behavioral breakage or alter an approved HARNESS contract.
HARNESS remains the authority for execution, reconciliation and completion.

## Response contract

The comparison response adds:

```json
{
  "impact": {
    "summary": {
      "changed_contract_nodes": 1,
      "changed_contract_relations": 0,
      "code_anchors": 1,
      "dependent_code": 2,
      "unresolved_contract_nodes": 0,
      "truncated": false
    },
    "anchors": [],
    "dependents": [],
    "unresolved": []
  }
}
```

Each anchor contains the current graph node projection and its contract evidence.
Each dependent additionally contains `distance`, `anchor_id` and an ordered
array of observed graph relationships in `path`.

## Acceptance scenarios

| ID | Expected result |
|---|---|
| CI-A01 | A signature change is reported once and an explicit design anchor becomes one code anchor |
| CI-A02 | Incoming call/dependency chains produce deterministic shortest paths and hop counts |
| CI-A03 | `contains`, outgoing provider dependencies and unrelated custom relations do not propagate impact |
| CI-A04 | A changed child inherits its nearest module anchor without reaching sibling capability anchors |
| CI-A05 | A stale or missing anchor is visible in `unresolved`; no code impact is guessed |
| CI-A06 | Reversed graph input returns the same result and neither snapshot nor graph is mutated |
| CI-A07 | The compare HTTP response preserves the exact delta and includes server-derived impact |
| CI-A08 | The browser renders anchors, dependents, paths and the empty-impact state without changing the graph |
| CI-A09 | Existing Python and JavaScript suites remain green |

## Non-goals

- Predicting runtime failures or assigning probabilistic severity.
- Comparing arbitrary Git revisions or source text.
- Replacing HARNESS contract reconciliation.
- Highlighting every affected node in the graph.
- Persisting impact results, which are derived from the current observed graph.
