# Architectural Layers and Semantic Zoom decision log

## SZ-D001 - Explicit level selection, automatic visual detail

Status: Accepted
Date: 2026-08-25

Topology never changes merely because the user zooms. The user explicitly
chooses an architectural level; zoom only changes how much text is rendered.
This avoids spatial jumps and makes the control reversible and predictable.

## SZ-D002 - Preserve Native as the default

Status: Accepted
Date: 2026-08-25

Existing Flow expansion, Focus, shortcuts and `G` remain unchanged until the
user chooses a layer. Introducing automatic architectural filtering on load
would silently redefine already validated navigation behavior.

## SZ-D003 - Implement the projector at the browser-owned draft boundary

Status: Accepted; amends Architecture Workbench `AW-D002` for `AW-004`
Date: 2026-08-25

The initial Workbench contract proposed `semantic_zoom.py`. Current evidence
shows that the authoritative active graph includes browser-local proposal nodes
and synchronous navigation state that the server does not own. A Python service
would require uploading the mutable graph on every interaction or duplicating
the draft. The implementation therefore uses a pure, DOM-free JavaScript class
`SemanticZoomProjector` in `static/semantic-zoom.js`.

This is a reviewed contract amendment, not an unrecorded deviation. Scenarios,
contracts and future HARNESS promotion must use the amended target path.

## SZ-D004 - Reuse real ancestors as representatives

Status: Accepted
Date: 2026-08-25

Coarse projections do not invent synthetic area or module nodes. Relationships
map to existing ancestors and aggregated edges retain their original relation
ids in `memberIds`. This keeps inspection and evidence navigation grounded in
the common graph.

## SZ-D005 - Suspend topology-changing shortcuts in explicit layers

Status: Accepted
Date: 2026-08-25

Inline expansion and architectural level projection are two different topology
controls. Running both at once would create hidden expansion state that is hard
to understand. Explicit layers remain inspectable and can open `G`, but normal
expand/collapse/trace interactions resume only in Native.
