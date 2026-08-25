# Connected proposal contracts traceability matrix

Status values: `Specified`, `Tested`, `Implemented`, `Rendered`, `Verified`,
`Blocked`.

| Requirement | Decisions | Planned implementation | Automated evidence | Acceptance | Status |
|---|---|---|---|---|---|
| PC-001 | PC-D001, PC-D005, PC-D006 | `static/proposal-contract.js` | Node contract tests | PC-A01, PC-A03, PC-A04 | Specified |
| PC-002 | PC-D002, PC-D006 | Add/Edit proposal dialog and `app.js` | Browser source assertions plus rendered form test | PC-A01, PC-A04 | Specified |
| PC-003 | PC-D001, PC-D004 | `explore/tools.py`, gateway history, `applyAgentGraphProposals` | Registry, gateway, MCP, and browser application tests | PC-A02, PC-A05 | Specified |
| PC-004 | PC-D004, PC-D005 | Connection derivation and proposal inspector | Node connection tests | PC-A05, PC-A06 | Specified |
| PC-005 | PC-D003, PC-D006, PC-D007 | Code workspace contract view | DOM/source tests and Playwright | PC-A03, PC-A04, PC-A05, PC-A09, PC-A10 | Specified |
| PC-006 | PC-D001, PC-D008 | Browser draft plus `mergeMissionDesign`, `desiredDesignState`, `designOperations` | Serialization and server integration assertions | PC-A01, PC-A07, PC-A08 | Specified |
| PC-007 | PC-D002 | Contract normalization and existing draft reconciliation | Legacy contract fixture | PC-A04 | Specified |
| PC-008 | All | Full suites and rendered acceptance log | Python, Node, syntax, diff checks, Playwright | PC-A01 through PC-A10 | Specified |

## Baseline evidence - 2026-08-25

- Graph Lab commit: `7a258b8`; worktree clean.
- HARNESS commit: `13d1ebe`; three unrelated untracked PNG files were preserved.
- HARNESS already stores and verifies exact node contract fields.
- Graph Lab `desiredDesignState` currently serializes only identity, visual level,
  provenance, location, intent, parent, locator, and description.
- The current Add/Edit dialog captures only name, kind, and parent.
- Current `ProposeNode` transports only name, kind, parent, and description.
- `renderCodePanel` returns without rendering when a selected node has no source.
- A live MCP Architecture Workbench proposal demonstrated the failure: it was
  reviewable in the graph but its conceptual subgraph did not explain concrete
  implementation anchors and selecting its modules produced no code view.

## Commit evidence

| Commit | Scope | Requirements |
|---|---|---|
| Pending | Specification, decisions, and traceability baseline | PC-001 through PC-008 |

## Rendered acceptance evidence

Pending implementation. Rendered evidence must record the exact proposal used,
its observed anchor, the visible interface/docstring, the disconnected warning
case, reload behavior, and browser console state.
