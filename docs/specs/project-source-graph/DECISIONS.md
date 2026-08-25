# Project source graph decision log

## PSG-D001 - Represent non-Python sources as file nodes

Status: Accepted
Date: 2026-08-25

JavaScript, TypeScript, CSS and HTML sources use the observed kind `file` until a
language adapter can justify richer symbols. Labelling every asset as a module or
guessing functions from text would overstate the available evidence.

## PSG-D002 - Keep a small explicit extension allowlist

Status: Accepted
Date: 2026-08-25

The first boundary covers Python plus code-bearing web sources used by Graph Lab.
Markdown, lock files, datasets and arbitrary text are not included merely because
they are decodable. Additional language adapters may extend the list deliberately.

## PSG-D003 - Reuse directory containment without changing Python packages

Status: Accepted
Date: 2026-08-25

Directories continue to use the existing `package` visual container so file nodes
can share the Explorer hierarchy with Python modules. This is a visual containment
model; it does not assert that a static directory is a Python package.

## PSG-D004 - One enumeration for graph, cache and source

Status: Accepted
Date: 2026-08-25

Extraction, fingerprinting and `/api/source` must not maintain separate extension
rules. A file visible in the graph but unavailable in Code, or served without
invalidating the graph cache, would recreate the same integrity failure at a new
boundary.

## PSG-D005 - Defer semantic JavaScript analysis

Status: Accepted
Date: 2026-08-25

This change exposes honest file-level evidence only. Imports, exports, classes and
calls remain the responsibility of the planned TypeScript/JavaScript adapter.
