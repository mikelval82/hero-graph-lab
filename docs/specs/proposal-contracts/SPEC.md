# Connected proposal contracts specification

Status: Approved for implementation
Date: 2026-08-25
Graph Lab baseline: `7a258b8`
HARNESS contract baseline: `13d1ebe`
Scope: Graph Lab proposal authoring, MCP delivery, rendered inspection, and lossless HARNESS synchronization

## Problem

Graph Lab can add proposed nodes and relationships, but a proposal node currently
contains little more than its name, kind, parent, and optional description. The
browser does not capture the exact interface fields already supported by HARNESS,
the MCP proposal schema cannot send them, and `desiredDesignState` drops them when
the user saves the map. Selecting a node without observed source leaves the Code
panel empty. Relationships can visually connect a proposed subgraph, but the UI
does not explain which links reach observed code or warn when the proposal has no
implementation anchor.

As a result, the map is useful as a sketch but is not yet a usable design contract:
the user cannot understand the intended interface, how it integrates with current
code, what behavior it promises, or what an implementation agent must satisfy.

## Goals

1. Make every code-oriented proposal capable of expressing the exact structural
   and behavioral contract already understood by HARNESS.
2. Preserve the same fields whether a proposal comes from the graph editor, the
   Explore chat, or Codex through MCP.
3. Make the relationship between proposed design and observed code explicit and
   inspectable without pretending that proposed source already exists.
4. Render a readable interface preview, docstrings, responsibilities, acceptance
   criteria, and connection evidence when a proposed node is selected.
5. Synchronize the enriched contract to HARNESS without translating it into a
   weaker parallel schema.
6. Keep incomplete drafts editable while making omissions and disconnected design
   visible before approval.

## Non-goals

- Generate complete implementation code during proposal creation.
- Write `.py`, `.pyi`, TypeScript, or JavaScript stubs into the repository before
  contract approval and execution.
- Move design approval, version authority, task slicing, or verification out of
  HARNESS.
- Implement the future TypeScript/JavaScript analyzer in this increment.
- Require every semantic relationship to be a deterministic verification gate.
- Replace the existing source viewer or mission contract cards.

## Contract model

Graph Lab shall use the HARNESS field names at its synchronization boundary:

- `kind`;
- `target_path`;
- `qualified_name`;
- `signature`;
- `docstring`;
- `description`;
- `satisfies`;
- `acceptance`.

The browser may retain its existing visual fields such as `designDescription`,
but normalization must be centralized and lossless. Arrays are bounded lists of
trimmed, unique, non-empty strings. Paths are repository-relative and use `/`.

An interface preview is a derived view of this structured contract. It is not
source evidence and must be labelled as proposed.

## Requirements

### PC-001 - One normalized proposal contract

Graph Lab shall provide a small transport-independent JavaScript module that:

- normalizes proposal contract fields;
- computes field-level completeness issues by node kind;
- derives interface-preview text;
- derives direct and component-level connections to observed code.

The graph editor, MCP application path, HARNESS synchronization, and rendered
inspector shall use this same contract rather than maintaining independent field
rules.

For the first increment, code-bearing nodes are `module`, `class`, `function`, and
`method`. A package may describe an architectural grouping without a signature.

### PC-002 - Rich proposal authoring

The Add/Edit proposal dialog shall allow the user to provide:

- name and exact kind, including package;
- containment parent;
- intended repository-relative target path;
- qualified name;
- declaration or signature where applicable;
- responsibility description;
- docstring;
- linked requirement identifiers;
- behavioral acceptance criteria.

The form shall not discard existing values when editing. It may save an incomplete
draft, but the missing obligations must remain visible in the inspector.

### PC-003 - Equivalent MCP and chat proposal payloads

`ProposeNode` shall accept and emit the same optional structured contract fields.
The shared registry remains authoritative for REST chat and MCP. The Graph Tool
Gateway history and browser proposal application shall retain those fields.

The Propose-mode instruction shall require an agent to inspect relevant observed
nodes, populate all contract fields it can justify, and create explicit
relationships to observed implementation anchors. It shall not invent a path,
signature, or code connection when evidence is insufficient; unresolved fields
must remain visibly incomplete.

### PC-004 - Observed-code connection evidence

For a selected proposed node, Graph Lab shall derive and display:

- direct incoming and outgoing relationships;
- whether each endpoint is observed or proposed;
- observed ancestors that provide structural containment;
- observed implementation anchors reachable through the proposal component.

Project-root containment alone is a structural placement, not a sufficient
implementation connection. A proposal component with no relationship to an
observed package below the root, module, class, function, or method shall show a
clear `No observed implementation connection` issue.

The application shall not add speculative relations automatically. Connections
remain explicit reviewed graph changes.

### PC-005 - Contract inspector and interface preview

Selecting a proposed node without source shall open a Proposal Contract view in
the existing Code workspace instead of leaving it blank. The view shall show:

- proposal status and provenance;
- responsibility and intended target;
- a generated Python-like interface preview for the current Python-first contract;
- docstring and child method/function declarations when available;
- requirement identifiers and acceptance criteria;
- observed/proposed connections with direction and relationship;
- completeness and integration issues.

The preview must be escaped text rendered through DOM APIs and must never be
presented as repository source. Selecting observed code shall preserve the
existing source viewer.

### PC-006 - Lossless browser persistence and HARNESS synchronization

The browser-local design draft shall persist enriched node fields across reloads.
`mergeMissionDesign`, `desiredDesignState`, and `designOperations` shall round-trip
all contract fields supported by HARNESS. Update comparison shall include those
fields, including array content.

Saving the map remains explicit. Rendering or editing a local contract shall not
implicitly synchronize HARNESS.

### PC-007 - Backward-compatible incomplete drafts

Existing stored proposals and MCP callers without enriched fields shall continue
to load and remain editable. They shall be normalized to empty contract values and
shown as incomplete; they shall not be rejected, guessed, or silently reported as
implementation-ready.

### PC-008 - Verification boundary

Automated tests shall cover normalization, interface rendering, completeness,
connection derivation, MCP field transport, browser application, persistence, and
HARNESS-operation serialization. Completion also requires a rendered browser test
showing an enriched connected proposal and an intentionally disconnected proposal.

Unit tests or the presence of fields in source code are not sufficient evidence
for the rendered interaction.

## Acceptance scenarios

| ID | Scenario | Expected result |
|---|---|---|
| PC-A01 | Add a proposed method with path, qualified name, signature, docstring, requirement, and acceptance criterion | Reload preserves every field and Edit shows the same values |
| PC-A02 | Propose the same structured method through MCP | The browser-local node retains the exact contract fields and provenance |
| PC-A03 | Select a proposed class with proposed child methods | The Code workspace shows a labelled contract preview containing the class docstring and child signatures |
| PC-A04 | Select an old proposal containing only label and kind | The proposal remains usable and the inspector lists the missing contract fields |
| PC-A05 | Connect a proposal to an observed module and inspect it | The connection list names the observed module, direction, and relation; the disconnected warning is absent |
| PC-A06 | Inspect a subgraph connected only to the project root | The inspector reports that no observed implementation connection exists |
| PC-A07 | Save an enriched map to an active mission | HARNESS receives kind, path, qualified name, signature, docstring, satisfies, acceptance, and description unchanged |
| PC-A08 | Reopen an enriched HARNESS design revision | Graph Lab reconstructs the same proposal contract and preview |
| PC-A09 | Select normal observed source after inspecting a proposal | The existing source viewer opens the correct lines without proposal-preview residue |
| PC-A10 | Inspect preview text containing HTML characters | It is displayed as text and no markup or script is executed |

## Delivery sequence

1. Record requirements, accepted decisions, traceability, and baseline evidence.
2. Add failing unit and integration tests for the normalized contract and transport.
3. Implement the shared proposal-contract module and enrich MCP/browser data paths.
4. Extend Add/Edit and lossless HARNESS synchronization.
5. Render the Proposal Contract inspector and connection evidence.
6. Run complete Python/JavaScript validation and rendered Playwright acceptance.
7. Update traceability and commit each independently reviewable increment.

## Completion boundary

The increment is not complete merely because HARNESS already supports the fields
or because Graph Lab serializes them. It is complete only when a human can create
or receive a proposal, see how it connects to observed code, inspect its interface
and intent, reload it, and save it without losing contract information.
