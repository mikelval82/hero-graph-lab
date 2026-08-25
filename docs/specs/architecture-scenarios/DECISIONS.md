# Architecture Scenarios decision log

## AS-D001 - Snapshot only the design overlay

Status: Accepted
Date: 2026-08-25

Scenarios store proposed/modified nodes and design relationships plus referenced
observed endpoints. Copying the complete extracted graph would make every
scenario large, duplicate rebuildable evidence and create false diffs whenever
unrelated source code changes.

## AS-D002 - Persist beside Graph Lab state

Status: Accepted
Date: 2026-08-25

Scenario JSON uses the existing ignored `state` boundary. It must not dirty the
selected repository and does not require an active HARNESS mission. The document
is partitioned by the resolved project path.

## AS-D003 - Compare exact contract fields before semantic inference

Status: Accepted
Date: 2026-08-25

The first comparison is deterministic and field-level. It does not ask an LLM to
decide whether two differently named nodes are conceptually equivalent. That
inference would need confidence, provenance and human review.

## AS-D004 - Use a modal workspace

Status: Accepted
Date: 2026-08-25

Scenario capture and comparison are occasional design actions, so a dialog keeps
the graph as the dominant surface. A permanent fifth panel would repeat the
space-allocation problems already corrected elsewhere in the UI.

## AS-D005 - No apply operation in the first slice

Status: Accepted
Date: 2026-08-25

Applying one alternative requires conflict policy for the current draft and
HARNESS revision state. Capture and comparison provide independent value without
introducing that unsafe mutation path prematurely.

## AS-D006 - Removed observed nodes belong to the design overlay

Status: Accepted
Date: 2026-08-25

The implementation makes explicit that a removed observed node is a design
change and must be captured. Excluding it would make an alternative appear less
destructive than it is. This clarifies AS-001 without expanding the snapshot to
unrelated observed code.
