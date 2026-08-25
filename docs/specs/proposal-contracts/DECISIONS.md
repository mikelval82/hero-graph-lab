# Connected proposal contracts decision log

This log is append-only. Superseded decisions remain visible and identify their
replacement.

## PC-D001 - Reuse the HARNESS contract vocabulary

Status: Accepted
Date: 2026-08-25

Graph Lab will author and render the node fields already owned by HARNESS instead
of introducing a second `proposal_spec` object with different names. A parallel
schema would require translation, make partial loss likely, and allow editor and
executor contracts to drift.

## PC-D002 - Keep incomplete proposals editable but visibly incomplete

Status: Accepted
Date: 2026-08-25

Research and early design are allowed to be incomplete. The browser will not block
local draft creation merely because a signature, requirement, or code anchor is
unknown. It will calculate explicit issues and must not label such a proposal as
ready. Approval and execution remain the stronger HARNESS gates.

## PC-D003 - Render virtual interfaces without creating source stubs

Status: Accepted
Date: 2026-08-25

The Code workspace will render a derived, clearly labelled contract preview for a
proposal. It will not create `.py` or `.pyi` files. Writing stubs during design
would pollute observed extraction and create a false impression of implementation.

## PC-D004 - Require explicit observed-code relationships

Status: Accepted
Date: 2026-08-25

Graph Lab will explain existing proposal relationships and warn about missing
implementation anchors, but it will not infer or add semantic edges automatically.
The agent or human must select justified observed endpoints. Project-root
containment communicates placement only and does not count as an implementation
connection.

## PC-D005 - Use one small pure JavaScript contract module

Status: Accepted
Date: 2026-08-25

Normalization, completeness, interface preview, and connection derivation belong
in a dependency-free module with Node tests. Keeping these rules inline in
`app.js`, `explore.js`, and `mission.js` would repeat conditionals across three
large scripts. A framework or client-side state library is not justified.

## PC-D006 - Python-like preview first, language adapters later

Status: Accepted
Date: 2026-08-25

The existing extractor and structural verifier are Python-first. This increment
will render Python-like declarations and preserve language-neutral contract fields.
The TypeScript/JavaScript adapter will later supply its own preview strategy; a
generic templating framework is premature now.

## PC-D007 - Preserve current source inspection behavior

Status: Accepted
Date: 2026-08-25

The proposal inspector shares the Code workspace but is a separate rendered state.
Observed nodes continue to open actual source lines. A proposed contract must not
overwrite `state.source`, masquerade as a file, or leak into source search.

## PC-D008 - Keep Save map explicit and HARNESS authoritative

Status: Accepted
Date: 2026-08-25

Browser storage remains the mutable local draft. The enriched payload reaches
HARNESS only through the existing Save map action. HARNESS remains responsible for
versioning, approval, task contracts, execution leases, and verification.

## PC-D009 - Reveal authored proposals outside transient navigation state

Status: Accepted
Date: 2026-08-25

Creating, editing, or receiving a proposal shall reveal it even when the current
Flow journey or graph scope would otherwise filter it out. Graph Lab clears the
transient Flow journey and, only when necessary, returns the scope to the project
root before expanding the proposal path. A deliberate design change must not look
lost merely because it was authored from a narrowed navigation context.

## PC-D010 - Serialize the HARNESS contract through the pure contract module

Status: Accepted
Date: 2026-08-25

The exact HARNESS-facing contract fields are derived by
`proposal-contract.js`, alongside normalization and completeness rules. Mission
layout metadata remains in `mission.js`. This creates a directly testable
transport boundary without moving mission authority into the browser module.
