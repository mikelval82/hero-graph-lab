# Connected proposal contracts traceability matrix

Status values: `Specified`, `Tested`, `Implemented`, `Rendered`, `Verified`,
`Blocked`.

| Requirement | Decisions | Planned implementation | Automated evidence | Acceptance | Status |
|---|---|---|---|---|---|
| PC-001 | PC-D001, PC-D005, PC-D006, PC-D010 | `static/proposal-contract.js` | Six focused contract tests | PC-A01, PC-A03, PC-A04 | Tested and implemented |
| PC-002 | PC-D002, PC-D006 | Add/Edit proposal dialog and `app.js` | Server asset assertions plus rendered class/method authoring | PC-A01, PC-A04 | Rendered and implemented |
| PC-003 | PC-D001, PC-D004 | `explore/tools.py`, gateway history, `applyAgentGraphProposals` | Registry, gateway, Explore, HTTP and real STDIO MCP protocol tests | PC-A02, PC-A05 | Tested and implemented |
| PC-004 | PC-D004, PC-D005 | Connection derivation and proposal inspector | Proposal component tests plus rendered connected/disconnected cases | PC-A05, PC-A06 | Rendered and implemented |
| PC-005 | PC-D003, PC-D006, PC-D007 | Code workspace contract view | Safe text preview test, server assertions and rendered class/method previews | PC-A03, PC-A04, PC-A05, PC-A09, PC-A10 | Partially verified; PC-A09 browser rerun open |
| PC-006 | PC-D001, PC-D008, PC-D010 | Browser draft plus `mergeMissionDesign`, `desiredDesignState`, `designOperations` | Exact payload test, array isolation, update comparison and integration assertions | PC-A01, PC-A07, PC-A08 | Implemented; rendered reload and live HARNESS round-trip open |
| PC-007 | PC-D002 | Contract normalization and existing draft reconciliation | Legacy node normalization and incomplete-contract tests | PC-A04 | Tested and implemented |
| PC-008 | All | Full suites and rendered acceptance log | Python 41 passed; Node 38 passed; syntax and diff checks passed | PC-A01 through PC-A10 | Automated gates passed; rendered acceptance partial |

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
| `12a0a8d` | Normalized contract, rich authoring, MCP transport, synchronization, and inspector | PC-001 through PC-007 |
| `119e453` | Reveal proposals hidden by a transient Flow journey or narrowed scope | PC-002, PC-005 |
| `4c58bf4` | Central HARNESS serializer and enriched STDIO MCP protocol proof | PC-003, PC-006, PC-008 |

## Rendered acceptance evidence - 2026-08-25

The running Gemini-backed application at `http://127.0.0.1:8765/` was exercised
against the real Graph Lab repository:

- A proposed `ProposalContractInspector` class was created beneath observed
  `extractor.py`, targeting `src/hero_graph_lab/proposal_inspector.py`, with a
  qualified name, responsibility, docstring, requirements and acceptance
  criteria. Its inspector named `extractor.py
  (src/hero_graph_lab/extractor.py)` as an observed anchor via `contains` and
  reported `Contract ready for design review`.
- A proposed child method `render_contract` was created with the signature
  `(self, node_id: str) -> str`, docstring, requirement and acceptance criterion.
  The selected class preview included that exact child declaration and the
  selected method rendered its own virtual interface.
- A complete `DisconnectedScenario` module placed only beneath the project root
  rendered `Contract incomplete · 1` and the exact issue `No observed
  implementation connection.` Root placement was therefore not mistaken for
  implementation integration.
- Creating and editing proposals from a narrowed Flow journey exposed a real UI
  fault: the new node existed in the draft but remained filtered from the graph.
  Commit `119e453` clears that transient journey, restores root scope only when
  needed, expands the tree path and keeps the proposal selected. The rerun showed
  `render_contract` in the navigation graph with an empty Flow journey.
- No application exception was observed. Two connection-reset messages occurred
  only while the local server was deliberately restarted and are not counted as
  application-console failures.

The final reload/source-return rerun is still open. The replacement integrated
Browser plugin currently fails during its own bootstrap because its trusted
runtime rejects `browser-service.mjs`; this occurs before Graph Lab is opened.
The earlier rendered checks above used the working browser session before that
plugin-level failure. PC-A01 reload, PC-A09 source return, and live HARNESS
PC-A07/PC-A08 therefore remain explicitly unclaimed.

## Automated implementation evidence - 2026-08-25

- Python: `41 passed` with the cache provider disabled.
- JavaScript: `38 passed`, including six proposal-contract tests.
- Every static JavaScript file passed `node --check`.
- `git diff --check` passed.
- The real STDIO MCP smoke listed the enriched `ProposeNode` schema, called it
  with every structured field, and verified the staged action retained each
  value unchanged.
- Exact HARNESS payload serialization is unit-tested, including defensive array
  copies; a live active-mission Save map/reopen round-trip remains open and is
  not implied by these automated results.
