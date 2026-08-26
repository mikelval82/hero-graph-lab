# TypeScript and JavaScript adapter traceability

| Requirement | Decisions | Planned implementation | Evidence | Status |
|---|---|---|---|---|
| TSA-001 | TSA-D001 | suffix-to-grammar parser selection | Adapter dialect fixture tests | Verified |
| TSA-002 | TSA-D002, TSA-D007 | script module nodes and source ranges | Adapter and extractor integration tests | Verified |
| TSA-003 | TSA-D003, TSA-D006 | declaration collector | TS/TSX declaration fixture test | Verified |
| TSA-004 | TSA-D003, TSA-D005 | relative module resolver | ES and CommonJS dependency fixture test | Verified |
| TSA-005 | TSA-D003, TSA-D004 | bounded call resolver | Positive and negative call fixture assertions | Verified |
| TSA-006 | TSA-D003, TSA-D004 | stable deduplication and error tolerance | malformed, reversed-input and repeated real-frontend tests | Verified |
| TSA-007 | TSA-D002 | extractor dispatch and compatibility tests | 54-test Python regression suite | Verified |
| TSA-008 | TSA-D005, TSA-D006, TSA-D007 | existing graph/UI consumers and small kind styling | 40-test JavaScript suite; rendered check pending | In progress |
| TSA-009 | TSA-D001 | bounded Python dependencies | aligned 0.23 wheel install and repeated static extraction | Verified |
| TSA-010 | TSA-D008 | one-level root IIFE statement normalization | IIFE fixture plus exact real-module symbol assertions | Verified |
| TSA-011 | TSA-D009 | explicit object/global export index | Exported, aliased, private and unknown-member assertions | Verified |
| TSA-012 | TSA-D009, TSA-D010 | global API alias dependency and call resolver | Positive and negative cross-module relation assertions; live MCP smoke | Verified |

## Baseline evidence - 2026-08-26

- Graph Lab commit `f93c413`; worktree clean.
- `project_source_files` already enumerates all target suffixes and excludes
  generated/dependency directories.
- `extract_project_graph` emits Python semantics but one `file` node for every
  non-Python source.
- `/api/source` and graph cache already share `project_source_files`.
- Flow already aggregates non-`contains` relationships, and the graph tools
  consume the common graph without language-specific branches.
- No JavaScript parser is installed by the project baseline.
- The official Tree-sitter packages installed successfully as Windows CPython
  wheels in the development environment.
- Rendered acceptance is currently at risk because the in-app Browser runtime
  rejects its installed service path before navigation. This remains an external
  validation blocker, not permission to substitute endpoint tests for TSA-A09.

## Implementation evidence - 2026-08-26

- Official JavaScript, TypeScript and TSX grammars are selected by suffix behind
  `TypeScriptGraphAdapter`; `extractor.py` remains the sole project orchestrator.
- Fixture coverage verifies declarations, containment, relative ES/CommonJS
  dependencies, conservative calls, malformed syntax and deterministic order.
- A real-frontend regression extracts every `static/*.js` file twice and checks
  the exact `renderCodePanel` source anchor.
- Five consecutive real-static extractions returned identical `205` nodes and
  `509` edges after aligning the Tree-sitter core and grammar ABI on 0.23.
- Full automated regression: `54` Python tests and `40` JavaScript tests pass.
- A resolved-root Graph Lab smoke completed in `0.472 s` with `621` nodes and
  `1423` edges; `app.js` and `renderCodePanel` were present with exact ranges.
- An isolated HTTP E2E served the TypeScript/TSX fixture on port 8766: its graph
  contained `24` nodes and `31` edges, including an interface, a TSX component,
  the expected module dependency and imported call; `/api/source` delivered the
  referenced TypeScript source.
- The main Gemini process was restarted on port 8765. Its live graph contains
  the `app.js` module and `renderCodePanel`; the configured Graph Lab MCP found
  the same function and read its exact source range.
- Rendered acceptance remains pending: after the restart, the in-app Browser
  still rejected its own installed service path as untrusted before navigation.
  No API or MCP result is counted as visual evidence.

## Real-project gap evidence - 2026-08-26

- Two complete extractions of `C:\Users\MikelValCalvo\hero-graph-lab` were
  identical and completed in `0.853 s` and `0.866 s`.
- The thirteen runtime `static/*.js` modules exposed `192` symbols and `304`
  local calls, but nine root-IIFE modules exposed no declarations at all.
- There were zero cross-module relationships among the runtime scripts because
  their authored `globalThis` API surfaces were outside the original adapter
  contract.
- `flow-navigation.js` contains `normalizeRelation` on line 2, while live MCP
  graph search returned no node for that declaration. This is a functional gap,
  not merely a rendered-UI problem.

## IIFE and global API completion evidence - 2026-08-26

- The fixture proves that only the direct body of a root IIFE becomes module
  scope: its public and private direct declarations are extracted while a
  nested function remains nested and absent from the module symbol index.
- `Object.freeze({...})`, direct global assignments and local API-object aliases
  establish an authored global API surface. Tests prove both aliased and direct
  global calls, and reject private members and unknown namespaces.
- All thirteen runtime `static/*.js` modules now expose declarations: opaque
  IIFE modules fell from `9` to `0`, and their total symbol count rose from
  `192` to `317`.
- Runtime-script semantics now contain `452` `calls`, `317` `contains` and `18`
  `depends_on` edges. Of those, `28` calls and all `18` dependencies cross a
  module boundary; no HTML load-order relationship was synthesized.
- Two final complete repository extractions were structurally identical,
  completed in `0.391 s` and `0.405 s`, and returned `774` nodes and `1774`
  edges.
- The live graph exposes `flow-navigation.normalizeRelation` at line 2 and
  `graph-views.flowGraph` at line 96, does not flatten nested
  `appendChildren`, links `app` to `flow-navigation`, and resolves
  `app.stopDrag -> flow-navigation.nodeClickTransition`.
- The configured Graph Lab MCP independently found `normalizeRelation` and
  returned `nodeClickTransition` among the outgoing neighbors of `stopDrag`.
- The Flow projection model remains bounded after adding these semantics: the
  root view contains `3` visible nodes and `3` aggregated edges; a static-module
  scope contains `25` visible nodes and `35` edges. These are model-level
  checks, not rendered-browser evidence.
- Current automated regression is `54/54` Python tests and `40/40` JavaScript
  tests. Rendered acceptance remains pending because the in-app Browser rejects
  its own installed service path before navigation.
