# Graph Lab MCP adapter specification

Status: Approved for implementation
Baseline: `d6958ff`
Scope: Graph tools, loopback API, MCP STDIO adapter, and proposal delivery

## Problem

Codex can already operate Graph Lab through browser control and ad-hoc HTTP
requests, but the graph is not exposed as a discoverable, typed tool set. The
Explore chat already has the required graph and proposal tools. Reimplementing
those rules in an MCP server would create contract drift, while routing the
browser chat through MCP would add a transport hop without changing its
capabilities.

## Goals

1. Expose the current graph tools to local Codex clients through MCP.
2. Keep the Explore browser chat on its existing REST contract.
3. Execute Explore and MCP calls through the same tool registry and active
   Graph Lab project.
4. Deliver MCP proposals to the browser as reviewable, browser-local draft
   actions without editing source files or synchronizing HARNESS.
5. Preserve explicit traceability from requirement to decision, code, test,
   rendered behavior, and commit.

## Non-goals

- Replace Gemini or another Explore model provider with Codex.
- Make Graph Lab or its MCP endpoint remotely accessible.
- Let MCP tools edit project source files.
- Save a proposal to HARNESS without the existing explicit **Save map** action.
- Replace the browser REST API with MCP.
- Introduce a second graph implementation or proposal schema.

## Requirements

### MCP-001 - One authoritative tool contract

The existing `ExploreToolRegistry` shall remain the source of truth for tool
names, descriptions, input schemas, validation, output bounds, and proposal
actions. REST-backed Explore and MCP shall not maintain independent graph rules.

### MCP-002 - Local STDIO adapter

Graph Lab shall provide an MCP STDIO entry point compatible with Codex. The
adapter shall expose the registry tools and delegate calls to the active Graph
Lab loopback server so that MCP observes the project selected in the web UI.

The adapter shall fail with an actionable error when Graph Lab is unavailable;
it shall not silently extract a different project.

### MCP-003 - Stable REST chat boundary

The browser Explore chat shall continue to use `/api/explore/...`. Its provider,
session, tool-loop, and response contract shall remain unchanged except for
receiving the shared registry dependency explicitly where needed.

### MCP-004 - Bounded loopback tool gateway

The Graph Lab server shall expose a loopback tool gateway used by the MCP
adapter. It shall:

- accept only registered tool names and JSON-object arguments;
- execute against the active project and current extracted graph;
- apply existing project path containment and proposal validation;
- return structured JSON errors without exposing credentials;
- reject oversized requests through the existing request-size boundary.

The gateway is an adapter, not a second tool implementation.

### MCP-005 - Reviewable proposal inbox

Successful MCP `ProposeNode` and `ProposeRelation` calls shall append their
existing action payloads to a server-side in-memory inbox with monotonic
revision numbers. The browser shall poll the inbox, apply unseen actions through
`applyAgentGraphProposals`, and acknowledge only actions it accepted.

Delivery shall be idempotent: retrying an unacknowledged action must not create
duplicate draft nodes or relationships. Changing the active project shall clear
the inbox so proposals cannot cross project boundaries.

### MCP-006 - Persistence and provenance boundary

MCP proposals shall use the existing browser-local design draft and `NEW`
provenance. Tool execution shall not write project source, browser storage, or
HARNESS directly. **Save map** remains the only explicit HARNESS synchronization
step.

Restoring that draft shall reconcile its proposal and edit overlay onto the
freshly extracted graph. A stored draft must not replace the current extraction
wholesale or hide code nodes added since the last browser save.

### MCP-007 - Tool safety metadata and Codex policy

Graph and project inspection tools shall be advertised as read-only. Proposal
tools shall be advertised as writes so Codex can apply a write-approval policy.
The server instructions shall state the proposal and persistence boundaries.

### MCP-008 - Project-scoped operation

Documentation shall provide a project-scoped Codex configuration and explain
the required Graph Lab server lifecycle. Machine-specific credentials shall not
be committed. Configuration performed outside the repository must be reported
separately from repository commits.

### MCP-009 - Validation gates

Completion requires:

- unit tests for shared registry execution and proposal inbox transitions;
- HTTP tests for tool execution, validation, delivery, acknowledgement, and
  project-change isolation;
- an MCP protocol smoke covering initialize, tools/list, and tools/call;
- the complete Python and JavaScript automated suites;
- `node --check` and `git diff --check`;
- a rendered browser check that an MCP proposal appears as a navigable `NEW`
  draft while Explore chat still responds through REST.

## Acceptance scenarios

| ID | Scenario | Expected result |
|---|---|---|
| MCP-A01 | Start the STDIO adapter while Graph Lab is available | MCP initializes and lists the registry tools with input schemas. |
| MCP-A02 | Call a graph query tool through MCP | The result reflects the project currently selected in Graph Lab. |
| MCP-A03 | Call an unknown tool or invalid arguments | The call fails without changing the graph or proposal inbox. |
| MCP-A04 | Propose a node and a relation through MCP | Both validated actions enter the inbox in revision order. |
| MCP-A05 | Leave an action unacknowledged and poll twice | The browser receives the same action identity and creates no duplicate. |
| MCP-A06 | Accept and acknowledge MCP proposals | They remain in the browser-local draft and disappear from the pending inbox. |
| MCP-A07 | Change the selected project | Pending proposals from the previous project are discarded. |
| MCP-A08 | Use Explore after enabling MCP | Explore still creates and answers its REST session normally. |
| MCP-A09 | Inspect an MCP proposal in Explorer and graph views | The `NEW` node is visible and navigable under existing proposal rules. |
| MCP-A10 | Stop Graph Lab and call a tool | MCP returns an actionable connection error and does not use stale data. |
| MCP-A11 | Reload an older browser draft after the extracted graph gains nodes | Draft proposals remain, newly extracted nodes appear, and MCP proposals can target those current nodes. |

## Delivery sequence

1. Record requirements, architecture decisions, and the traceability matrix.
2. Add failing contract tests for the shared gateway, inbox, and MCP protocol.
3. Implement the loopback gateway and proposal inbox over the current registry.
4. Implement the STDIO MCP adapter with the official Python MCP SDK.
5. Add browser delivery and project-scoped operational documentation.
6. Run automated, protocol, and rendered acceptance checks; close traceability.

## Completion boundary

Passing registry or HTTP tests does not prove Codex integration or visible draft
delivery. The feature remains partially verified until both an MCP protocol
client and the rendered browser have exercised the full proposal path.
