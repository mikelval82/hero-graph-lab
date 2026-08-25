# Project source graph specification

Status: Approved for implementation
Date: 2026-08-25
Baseline: `3b66bc0`
Scope: observed project files required as honest proposal anchors

## Problem

Graph Lab extracts Python packages, modules and symbols, and `/api/source` serves
only Python files. The application itself contains important observed behavior in
`static/*.js`, `*.css` and `*.html`, but those files are absent from the graph and
Code workspace. Architecture proposals for Semantic Zoom, guided walkthroughs or
scenario visualization therefore cannot connect to their real implementation
files without inventing a Python anchor.

## Goals

1. Show supported non-Python source files as observed graph nodes beneath their
   real directory hierarchy.
2. Serve the same files through `/api/source` so selecting them opens their real
   content in the Code workspace.
3. Keep Python AST classes, functions, methods and call relationships unchanged.
4. Use one deterministic file enumeration for graph cache invalidation, graph
   extraction and source delivery.
5. Enable proposal contracts to name explicit observed JavaScript/UI anchors.

## Non-goals

- Parse JavaScript or TypeScript symbols in this increment.
- Infer imports, calls or dependencies from non-Python text.
- Treat documentation, generated output, dependencies or arbitrary binary files
  as source code.
- Implement the future TypeScript/JavaScript language adapter.

## Requirements

### PSG-001 - Bounded project source enumeration

`project_source_files` shall include Python and directly served web source
extensions: `.py`, `.js`, `.mjs`, `.cjs`, `.jsx`, `.ts`, `.tsx`, `.css`, `.html`
and `.htm`. It shall preserve the existing excluded-directory policy and stable
lexical ordering.

### PSG-002 - Python analysis remains Python-only

Python files shall retain their package/module/symbol AST extraction. Every
supported non-Python file shall produce one observed `file` node with source path
and line extent, plus directory containment. No symbol or semantic relationship
shall be guessed for those files.

### PSG-003 - Source delivery parity

`LabState.source`, graph cache fingerprinting and project graph extraction shall
consume the same supported project-file enumeration. Every observed file node
must therefore resolve to source content through `/api/source`.

### PSG-004 - Backward compatibility

`extract_python_graph` and `python_source_files` remain available to existing
callers. Python-only fixtures shall keep their existing graph semantics and test
expectations.

### PSG-005 - Proposal integration

A proposal connected to an observed non-Python `file` node shall count as an
observed implementation connection and the inspector shall display its real path.

## Acceptance scenarios

| ID | Scenario | Expected result |
|---|---|---|
| PSG-A01 | Open Graph Lab itself | `static/app.js`, `graph-projection.js`, `diagrams.js` and other supported web files appear beneath the `static` directory |
| PSG-A02 | Select an observed JavaScript file | Code shows the current repository contents, not a proposal preview |
| PSG-A03 | Inspect the JavaScript file node | It contains no invented class/function/call children |
| PSG-A04 | Change a supported web source file | The graph cache fingerprint changes and the refreshed source is served |
| PSG-A05 | Connect an Architecture Workbench proposal to a JavaScript file | The proposal inspector names that file and does not report a disconnected contract |

## Completion boundary

The change is complete only when the graph and source endpoints agree on the
supported files and a rendered proposal can use a real JavaScript file as its
implementation anchor. Source-string assertions alone are insufficient for the
last scenario.
