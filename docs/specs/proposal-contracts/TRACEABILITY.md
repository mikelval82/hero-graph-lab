# Connected proposal contracts traceability matrix

Status values: `Specified`, `Tested`, `Implemented`, `Rendered`, `Verified`,
`Blocked`.

| Requirement | Decisions | Planned implementation | Automated evidence | Acceptance | Status |
|---|---|---|---|---|---|
| PC-001 | PC-D001, PC-D005, PC-D006 | `static/proposal-contract.js` | `proposal-contract.test.js` | PC-A01, PC-A03, PC-A04 | Tested and implemented |
| PC-002 | PC-D002, PC-D006 | Add/Edit proposal dialog and `app.js` | Server asset assertions; rendered form pending | PC-A01, PC-A04 | Implemented; rendered check pending |
| PC-003 | PC-D001, PC-D004 | `explore/tools.py`, gateway history, `applyAgentGraphProposals` | Registry, gateway, Explore, and server tests | PC-A02, PC-A05 | Tested and implemented |
| PC-004 | PC-D004, PC-D005 | Connection derivation and proposal inspector | Proposal component and observed-anchor tests | PC-A05, PC-A06 | Tested and implemented |
| PC-005 | PC-D003, PC-D006, PC-D007 | Code workspace contract view | Safe text preview test and server asset assertions; Playwright pending | PC-A03, PC-A04, PC-A05, PC-A09, PC-A10 | Implemented; rendered check pending |
| PC-006 | PC-D001, PC-D008 | Browser draft plus `mergeMissionDesign`, `desiredDesignState`, `designOperations` | Normalization and server integration assertions; live round-trip pending | PC-A01, PC-A07, PC-A08 | Implemented; live sync pending |
| PC-007 | PC-D002 | Contract normalization and existing draft reconciliation | Legacy node normalization and incomplete-contract tests | PC-A04 | Tested and implemented |
| PC-008 | All | Full suites and rendered acceptance log | Python 41 passed; Node 36 passed; syntax and diff checks passed | PC-A01 through PC-A10 | Automated gates passed; Playwright pending |

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
| `607b3a2` | Specification, decisions, and traceability baseline | PC-001 through PC-008 |
| Pending | Normalized contract, rich authoring, MCP transport, synchronization, and inspector | PC-001 through PC-007 |

## Rendered acceptance evidence

Pending implementation. Rendered evidence must record the exact proposal used,
its observed anchor, the visible interface/docstring, the disconnected warning
case, reload behavior, and browser console state.

## Automated implementation evidence - 2026-08-25

- Python: `41 passed` with the cache provider disabled.
- JavaScript: `36 passed`, including four proposal-contract tests.
- Every static JavaScript file passed `node --check`.
- `git diff --check` passed.
- Rendered and live HARNESS synchronization evidence remains open and is not
  implied by these automated results.
