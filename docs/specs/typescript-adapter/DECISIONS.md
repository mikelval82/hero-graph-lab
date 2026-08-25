# TypeScript and JavaScript graph adapter decision log

## TSA-D001 - Use official Tree-sitter Python wheels

Status: Accepted
Date: 2026-08-26

Python Tree-sitter exposes an error-tolerant concrete syntax tree and the
official JavaScript and TypeScript projects publish precompiled Python wheels.
This supports JS/JSX and the distinct TS/TSX grammars without introducing npm, a
frontend build, regex parsing or a long-running parser subprocess.

Validated development versions are `tree-sitter==0.26.0`,
`tree-sitter-javascript==0.25.0` and `tree-sitter-typescript==0.23.2`. Project
metadata uses compatible bounded ranges rather than an unbounded latest version.

## TSA-D002 - One adapter, no generic plugin framework

Status: Accepted
Date: 2026-08-26

`extractor.py` remains the project orchestrator and delegates supported script
files to one `TypeScriptGraphAdapter`. A registry, entry points or abstract
plugin lifecycle would add architecture before a second semantic adapter needs
it. The adapter still exposes a narrow, independently testable boundary.

## TSA-D003 - Two-pass project extraction

Status: Accepted
Date: 2026-08-26

The adapter first parses and indexes every supported script module, then emits
relations. This is the smallest design that can resolve relative imports and
imported calls without depending on input order or repeatedly parsing files.

## TSA-D004 - Prefer missing edges over guessed runtime behavior

Status: Accepted
Date: 2026-08-26

Only local, `this`, and statically imported targets are eligible call evidence.
Classic-script globals, arbitrary member calls and dependency injection are
ambiguous without binding/type analysis. Omitting those edges is more honest
than making Flow visually richer with false relationships.

## TSA-D005 - Model imports as `depends_on`

Status: Accepted
Date: 2026-08-26

The existing graph and UI already support `depends_on`, and module diagrams
aggregate every non-containment relation. Introducing a new `imports` kind would
add vocabulary without a distinct product behavior. Source-level call evidence
continues to use `calls`.

## TSA-D006 - Add observed interface and type kinds

Status: Accepted
Date: 2026-08-26

Mapping a TypeScript interface or alias to `class` would misstate the source;
omitting them would hide central architectural contracts. The common graph is
open to observed kinds, so `interface` and `type` are added with small visual
support. Proposal-authoring kinds remain unchanged in this increment.

## TSA-D007 - Preserve source delivery as the authority

Status: Accepted
Date: 2026-08-26

The adapter stores project-relative source paths and line ranges only. It does
not copy source text into graph nodes. `/api/source` remains authoritative for
the Code panel, and the existing shared file enumeration continues to drive
cache invalidation.
