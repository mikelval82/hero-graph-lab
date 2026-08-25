# Architectural Layers and Semantic Zoom specification

Status: Rejected after usability review
Date: 2026-08-25
Baseline: `0e4e2c2`
Parent contract: Architecture Workbench `AW-004`
Implementation status: Reverted; retained only as decision history

## Rejection outcome

The global level selector did not make the repository easier to understand. On
the live project it produced 65 nodes and 111 relations at Modules, 116/224 at
Types and 366/808 at Members. That duplicated existing scope, inline expansion,
Flow aggregation and `G` projection behavior while adding another topology
model. The user rejected the rendered result and the implementation was removed
through explicit revert commits.

This specification is historical evidence, not an active implementation plan.

## Problem

Graph Lab can expand containment and create temporary `G` projections, but it
cannot deliberately answer “show me only areas”, “show me modules” or “show me
types”. Visual zoom scales every node without changing the amount of text, so a
large fitted graph becomes visually noisy instead of semantically simpler.

## Original goal

Add an explicit architectural abstraction layer and zoom-dependent visual detail
without changing source identity, the browser-local design draft or the existing
`G` projection contract. The feature must help a user move between a system
overview and implementation detail while retaining evidence links.

## Requirements

### SZ-001 - Explicit architectural levels

A compact selector offers these levels:

| Level | Retained node kinds |
|---|---|
| Native | Existing Flow, Hierarchy or Focus behavior |
| Areas | `package` |
| Modules | `package`, `module`, `file` |
| Types | module-level kinds plus `class` |
| Members | all known kinds, including `function` and `method` |

The default is **Native**, so existing navigation does not change implicitly.
Unknown kinds are treated as member-level details rather than guessed into an
architectural category.

### SZ-002 - Deterministic read-only projection

`SemanticZoomProjector.project(graph, options)` returns a new graph for the
requested level, scope and view. It must:

- retain the original ids and contract fields of visible nodes;
- map hidden relation endpoints to their nearest retained ancestor;
- aggregate equivalent relationships with deterministic ids, counts and
  original `memberIds`;
- derive a stable content identity when the extracted source relationship has
  no id yet, as happens before browser normalization;
- retain status (`observed`, `proposed`, `modified`, `removed`) and relationship
  properties;
- honour the current scope and hidden-node state;
- never mutate its graph, option arrays or sets.

Hierarchy keeps containment only. Flow keeps containment and aggregated
relationships. Focus keeps the selected representative and its direct call
neighbors, preserving current Focus semantics.

### SZ-003 - Stable selection and restore

When a selected member is hidden by a coarser level, selection maps to its
nearest visible ancestor using that ancestor's real graph id. Graph Lab remembers
the source selection and restores it when the user returns to a level where it is
visible or to Native.

If the user explicitly selects another node while a layer is active, that action
cancels the pending restoration. Layer changes do not change scope, draft
contracts, view history, positions or hidden-node preferences.

### SZ-004 - Zoom-dependent semantic detail

Visual zoom changes text detail, not topology:

| Graph zoom | Detail | Visible text |
|---|---|---|
| below 45% | Overview | node label; no relationship labels |
| 45% through 89% | Context | node kind and label; relationship labels |
| 90% and above | Detail | node kind, label and status; relationship labels |

Crossing a threshold rerenders labels while preserving layout and scroll anchor.
Color, shape, selection and accessible labels remain available at every detail.

### SZ-005 - Interaction boundaries

An explicit architectural layer replaces inline expansion for the moment:

- `E`, double-click expansion, Collapse and call tracing are disabled;
- selection, code/contract inspection, relationship inspection and `G` remain
  available;
- while `G` is open it owns the canvas, disables the layer selector and restores
  the selected architectural layer when closed;
- returning to Native restores normal expansion controls.

This prevents two independent topology mechanisms from producing contradictory
visible state.

### SZ-006 - Compact standard control

The layer selector and current semantic-detail indicator live in the context bar
beside zoom. They must wrap on narrow widths and must not introduce a permanent
panel or reduce the graph viewport height.

### SZ-007 - Browser-owned projection boundary

The pure projector lives in `static/semantic-zoom.js`. It has no DOM access and
can be tested under Node. `app.js` owns state transitions; `graph-render.js` owns
detail rendering. No server endpoint or HARNESS change is introduced.

## Acceptance scenarios

| ID | Expected result |
|---|---|
| SZ-A01 | Areas shows package nodes only and aggregates a deep call between the correct packages |
| SZ-A02 | Modules includes packages, Python modules and web-source `file` nodes but no classes or members |
| SZ-A03 | Types includes classes; Members includes functions and methods |
| SZ-A04 | A selected method maps to its class/module/package and returns to the exact method in Native |
| SZ-A05 | Reversing input node/edge order produces the same projected ids, counts and member ids |
| SZ-A06 | Zooming across 45% and 90% changes text detail without changing visible node ids or selection |
| SZ-A07 | `G` temporarily owns the canvas and Restore returns to the same layer |
| SZ-A08 | Proposed and removed nodes/relationships keep their status in every level where they are represented |

## Non-goals

- Infer business domains from folder names or ask an LLM to classify layers.
- Persist a selected layer across browser reloads.
- Replace Flow, Hierarchy, Focus or interactive `G` projections.
- Change graph extraction or the common graph schema.
- Move, rename, approve or implement proposal contracts.

## Completion boundary

Completion requires pure projection and selection-transition tests, render-detail
tests, regression suites, live asset delivery and an interactive rendered check
of level switching, zoom thresholds and `G` restore. Automated tests alone do
not prove the final canvas behavior.
