# Graph Lab MCP adapter decision log

This log is append-only. Superseded decisions remain visible and point to their
replacement.

## MCP-D001 - Preserve REST for the browser chat

Status: Accepted
Date: 2026-08-14

The Explore UI is a browser client with an established REST session contract.
Routing it through MCP would add serialization and lifecycle failure modes but
would not add capabilities. Explore therefore remains on REST and shares the
tool implementation below the transport boundary.

## MCP-D002 - Use the registry as the domain boundary

Status: Accepted
Date: 2026-08-14

`ExploreToolRegistry` already owns graph queries, project-contained source
inspection, proposal schemas, and validation. The loopback gateway and MCP
adapter will translate transport messages only; neither may duplicate handlers
or proposal rules.

## MCP-D003 - Delegate STDIO MCP calls to the active Graph Lab server

Status: Accepted
Date: 2026-08-14

A standalone extractor-backed MCP process could drift from the project selected
in the UI. The Codex-facing process will instead use STDIO for MCP and loopback
HTTP for Graph Lab calls. This preserves one active-project authority and keeps
the MCP process simple. The explicit cost is that Graph Lab must be running.

## MCP-D004 - Use the official Python MCP SDK as an optional extra

Status: Accepted
Date: 2026-08-14

Hand-implementing JSON-RPC framing, initialization, capability negotiation, and
tool result types would create protocol risk unrelated to the graph experiment.
The MCP entry point will use the official Python SDK behind the `mcp` optional
dependency so the base web lab remains dependency-light.

## MCP-D005 - Keep MCP proposal delivery in memory until browser acceptance

Status: Accepted
Date: 2026-08-14

The authoritative draft already lives in browser storage. Persisting a second
server-side design document would create conflicting authorities. The server
will hold only a bounded, in-memory delivery inbox. Accepted proposals persist
through the existing browser draft; unaccepted proposals intentionally vanish
when Graph Lab stops.

## MCP-D006 - Acknowledge actions explicitly and require idempotent replay

Status: Accepted
Date: 2026-08-14

Polling can repeat after a network or browser interruption. Each inbox item will
have a stable revision and existing stable proposal identifiers. The browser
will acknowledge the highest contiguous accepted revision only after applying
the batch. Application must treat an already-present proposal identifier as a
successful replay rather than create a duplicate.

## MCP-D007 - Mark proposal tools as writes

Status: Accepted
Date: 2026-08-14

Although proposals do not edit source or HARNESS, they mutate the visible design
draft. MCP metadata and the recommended Codex configuration will therefore
distinguish read-only inspection tools from proposal writes.

## MCP-D008 - Do not claim current-session tool availability after configuration

Status: Accepted
Date: 2026-08-14

Writing Codex configuration does not alter the tool inventory of an already
running session. Repository validation will use an MCP protocol client. Codex
availability will be reported only after the extension has restarted and the
new server is actually listed or callable.

## MCP-D009 - Acknowledge accepted revisions explicitly

Status: Accepted; supersedes the acknowledgement detail in MCP-D006
Date: 2026-08-14

A batch can contain actions whose UI acceptance differs after a project or
browser-state transition. The browser therefore applies each delivered action
idempotently and acknowledges the explicit set of accepted revisions, rather
than advancing one highest-revision cursor. The stable action identity still
makes an interrupted replay safe.

## MCP-D010 - Retain bounded MCP action history in process memory

Status: Accepted; clarifies MCP-D005
Date: 2026-08-14

Acknowledgement removes an action from the delivery inbox but not from the
bounded in-memory MCP history. This lets a later MCP relation reference a node
that the browser has already accepted and lets graph queries see proposals made
through the same MCP process. The history is not a persistent design authority:
it is cleared on project change or process stop, while the browser draft remains
the persisted review state.
