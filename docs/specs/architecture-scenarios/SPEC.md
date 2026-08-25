# Architecture Scenarios A/B specification

Status: Approved for direct implementation
Date: 2026-08-25
Baseline: `36d5d2a`
Parent contract: Architecture Workbench `AW-003`

## Problem

Graph Lab has one mutable browser-local design draft. A user can discuss an
alternative with an LLM, but cannot preserve the current alternative, create a
second one and compare their structural and contract consequences. Replacing the
draft or relying on screenshots loses exact node fields, acceptance criteria and
observed-code anchors.

## Goal

Provide explicit immutable architecture scenarios and deterministic A/B
comparison while keeping the active graph draft unchanged. The result must help a
human understand what was added, removed or changed before choosing an
alternative; it does not approve or implement either scenario.

## Requirements

### AS-001 - Immutable bounded scenario snapshot

Capturing a scenario stores a server-assigned id, name, optional description,
creation time and an immutable design snapshot. The snapshot contains:

- proposed or modified design nodes with normalized contract fields;
- proposed, modified or removed design relationships;
- minimal descriptors for observed endpoints referenced by those relationships.

Unrelated observed source nodes, positions, zoom and transient navigation state
are excluded. Names and payload sizes are bounded.

### AS-002 - Project-scoped durable storage

Scenarios are stored in a JSON document beside Graph Lab's existing local state,
not inside the selected project. Each selected project has an independent
scenario collection. Writes use a temporary file and atomic replacement.

### AS-003 - Deterministic semantic comparison

`ArchitectureScenarioService.compare(left_id, right_id)` returns:

- added and removed nodes;
- nodes whose contract fields changed, with field-level before/after values;
- added and removed relationships;
- acceptance criteria added or removed across the comparison;
- summary counts and the immutable identifiers of both inputs.

Nodes use their scenario-stable graph id. Relationships use source, target,
relation kind and label. Input order and JSON object identity do not affect the
result.

### AS-004 - Local REST boundary

The server exposes project-scoped operations to list, capture, retrieve and
compare scenarios. Unknown ids, malformed snapshots and oversize inputs return
bounded `4xx` errors. The endpoints do not modify the graph draft or HARNESS.

### AS-005 - Compact browser workflow

A **Scenarios** action in the Draft tools opens a modal workspace. The user can:

- name and capture the current design as a scenario;
- select scenario A and B;
- compare them;
- inspect a concise summary and field-level changes.

The modal must not permanently consume graph canvas space.

### AS-006 - Shared contract normalization

Browser capture uses `proposal-contract.js` for node contract fields. The server
validates and normalizes again at its trust boundary. HTML-like labels and
docstrings are rendered as text.

### AS-007 - No implicit draft mutation

Capture and comparison never replace, merge or reposition the current graph.
Applying a scenario back to the draft is a separate future decision.

## Acceptance scenarios

| ID | Expected result |
|---|---|
| AS-A01 | Capture Workbench v2 as scenario A; every proposed contract and observed relationship endpoint is preserved |
| AS-A02 | Change one contract field and add one proposal, then capture scenario B |
| AS-A03 | Comparing A with B reports the exact added node and changed field without modifying the active draft |
| AS-A04 | Comparing B with A reverses additions and removals deterministically |
| AS-A05 | Reload the browser and list the same server-persisted scenarios |
| AS-A06 | A scenario for another selected project is not returned |
| AS-A07 | Malformed or oversize snapshots are rejected without corrupting stored scenarios |

## Non-goals

- Apply, merge or delete scenarios.
- Provide Git branching or source-code diffs.
- Ask an LLM to rank alternatives in this increment.
- Calculate transitive code impact; that belongs to `AW-005`.
- Synchronize scenarios to HARNESS before one is selected and promoted.

## Completion boundary

Completion requires unit tests for snapshot validation and comparison, HTTP
integration tests, JavaScript snapshot tests and a rendered capture/compare
workflow. Passing source-string assertions alone is not sufficient UI evidence.
