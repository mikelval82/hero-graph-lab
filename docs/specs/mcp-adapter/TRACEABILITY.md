# Graph Lab MCP adapter traceability matrix

Status values: `Specified`, `Tested`, `Implemented`, `Verified`, `Blocked`.

| Requirement | Decisions | Implementation | Automated evidence | Acceptance | Status |
|---|---|---|---|---|---|
| MCP-001 | MCP-D002 | `ExploreToolRegistry`, `GraphToolGateway`, injected Explore registry | `test_exposes_the_authoritative_registry_contract`; full Explore suite | MCP-A01, MCP-A08 | Implemented |
| MCP-002 | MCP-D003, MCP-D004 | `mcp_server.py`, `mcp_bridge.py`, `hero-graph-lab-mcp` | MCP STDIO protocol smoke | MCP-A01, MCP-A02, MCP-A10 | Verified |
| MCP-003 | MCP-D001 | Existing `/api/explore`; shared registry injection only | `test_explore_session_lifecycle`; full Explore suite | MCP-A08 | Verified |
| MCP-004 | MCP-D002, MCP-D003 | `/api/mcp/tools` gateway in `server.py` | Gateway and HTTP contract tests | MCP-A02, MCP-A03 | Verified |
| MCP-005 | MCP-D005, MCP-D009, MCP-D010 | Gateway history/inbox; `pollMcpProposals` | MCP proposal protocol smoke; gateway ordering/reset and HTTP ack tests; server source integration assertions; rendered Playwright replay | MCP-A04 through MCP-A07 | Verified |
| MCP-006 | MCP-D005, MCP-D010, MCP-D011 | Idempotent `applyAgentGraphProposals`; browser polling/ack; `reconcileStoredDesign` | Python integration assertions; all JS syntax checks passed | MCP-A06, MCP-A09, MCP-A11 | Verified in rendered browser |
| MCP-007 | MCP-D007 | MCP `ToolAnnotations` from gateway metadata | Registry metadata and MCP list tests | MCP-A01 | Verified |
| MCP-008 | MCP-D003, MCP-D008 | README setup; global local Codex registration | Host `codex mcp get/list`; MCP unavailable-server smoke | MCP-A01, MCP-A10 | Verified; extension restart pending |
| MCP-009 | All | Test suites and acceptance log | Python 32 passed; JavaScript 22 passed; syntax and protocol smoke passed | MCP-A01 through MCP-A11 | Verified |

## Validation evidence

### Baseline - 2026-08-14

- Commit: `d6958ff`.
- `python -m pytest`: 23 passed.
- `git diff --check`: passed.
- An absolute-path `node --check` loop was blocked by the managed workspace
  (`EPERM` resolving `C:\Users\MikelValCalvo`); relative-path syntax checks
  remain required at completion.
- No MCP dependency was installed at baseline.

## Commit evidence

| Commit | Scope | Requirements |
|---|---|---|
| `3177796` | Specification and decisions | MCP-001 through MCP-009 |
| `d27b0eb` | Shared registry gateway, inbox, loopback API, contract tests | MCP-001, MCP-003 through MCP-005 |
| `7c6bb4f` | Official SDK STDIO server and protocol smoke | MCP-002, MCP-004, MCP-007 |
| `3395de9` | Idempotent browser delivery and acknowledgement | MCP-005, MCP-006 |
| Pending | Operations documentation, Codex registration, and final validation | MCP-008, MCP-009 |

### Implementation validation - 2026-08-14

- Python suite after the STDIO and browser-delivery changes: 32 passed.
- MCP SDK installed and exercised: `mcp 1.29.0`.
- Protocol smoke covered initialize, tools/list, `GraphSearch`, and unavailable
  Graph Lab error propagation.
- The protocol smoke also staged `ProposeNode` and verified the resulting inbox
  action on a temporary live server.
- All static JavaScript files passed `node --check` outside the managed sandbox;
  22 Node tests passed.
- A live MCP client against `http://127.0.0.1:8765` initialized
  `hero-graph-lab`, listed 10 tools, and found `GraphToolGateway` through
  `GraphSearch`.
- Host `codex mcp get/list` reports `hero_graph_lab` enabled with the expected
  Python STDIO command. The already-running Codex session cannot acquire the new
  tool inventory until the IDE extension restarts.
- An earlier browser-discovery attempt returned no connected browser instances;
  the later Playwright run below closes the rendered acceptance gates.

### Rendered MCP acceptance - 2026-08-14

- Playwright loaded the active project from `http://127.0.0.1:8765/`.
- An actual MCP STDIO client created `VisualMcpNotifier` plus a
  `depends_on` relationship to `GraphToolGateway`; the browser initially
  rejected both because its persisted graph snapshot predated `gateway.py`.
- After MCP-D011, reload reconciled the local draft with the fresh 268-node
  extraction. The browser displayed `VisualMcpNotifier` in Explorer and Flow as
  a selected `proposed class` with `NEW`, and displayed `uses graph gateway`.
- The browser acknowledged revisions 1 and 2; `/api/mcp/proposals` returned an
  empty pending list.
- `G` opened the proposal in an interactive projection. `Esc` restored Flow
  with the proposal still selected, rendered, and keyboard-focused.
- A second reload retained the proposed node and relationship while also
  retaining the newly extracted `GraphToolGateway`, satisfying MCP-A11.
- Explore remained on `gemini / gemini-2.5-flash`, answered through its chat,
  and Playwright reported zero current console errors or warnings.
- The visual probe was deleted through the normal proposal UI after acceptance;
  selecting the project again reset the ephemeral MCP history and inbox to
  revision 0, leaving no probe in the browser draft or MCP delivery state.
