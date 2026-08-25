# TypeScript and JavaScript graph adapter specification

Status: Approved for direct implementation
Date: 2026-08-26
Baseline: `f93c413`
Parent contract: Architecture Workbench `AW-007`

## Problem

Graph Lab serves JavaScript and TypeScript sources and represents them as one
observed `file` node each. It cannot show their declarations, local call
structure or module dependencies. A mixed-language repository therefore looks
structurally complete at file level while most non-Python code remains opaque.

## Goal

Add deterministic, evidence-bounded JavaScript/TypeScript extraction behind the
existing project graph boundary. The adapter must enrich understanding without
changing Python semantics, inventing runtime behavior or adding a frontend build
system.

## Requirements

### TSA-001 - Supported dialects and parser boundary

The adapter supports `.js`, `.mjs`, `.cjs`, `.jsx`, `.ts` and `.tsx`. It uses
the official Tree-sitter JavaScript grammar for JS/MJS/CJS, the TypeScript
grammar for TS, and the TSX grammar for JSX/TSX through Python bindings. Parser
selection depends only on the file suffix.

### TSA-002 - Stable module identity and source evidence

Each supported script file becomes one observed `module` node instead of a
generic `file` node. Its id derives from the project-relative path, and it keeps
the exact source path and line extent used by `/api/source`. Directory/package
containment remains owned by `extractor.py`.

### TSA-003 - Bounded declaration extraction

The first increment extracts:

- named and default classes as `class`;
- TypeScript interfaces as `interface`;
- TypeScript type aliases and enums as `type`;
- top-level named functions and generator functions as `function`;
- top-level variables initialized with an arrow or function expression as
  `function`;
- class and interface methods as `method`.

Nodes retain exact start/end lines and containment. Anonymous expressions,
object-literal methods, nested local functions, fields, parameters and type
members other than method signatures are not graph nodes in this increment.

### TSA-004 - Relative module dependencies

Static ES imports, re-exports and CommonJS `require("...")` calls with a relative
string literal produce one `depends_on` relation between observed modules.
Resolution supports exact files, supported suffixes and `index` files. Bare npm
specifiers, aliases requiring project configuration, URLs and dynamic import
expressions do not create invented dependency nodes.

### TSA-005 - Evidence-bounded calls

`calls` relations are emitted only from an extracted function or method when a
target can be resolved uniquely as:

- a declaration in the same module;
- `this.method` in the same class;
- a named, default or namespace import whose relative target module and exported
  declaration are known.

Unqualified project-global names, arbitrary property calls, callbacks, dependency
injection and runtime dispatch are not guessed. Call order is not represented.

### TSA-006 - Determinism, duplicates and parser errors

Input order must not affect nodes or relations. Duplicate evidence collapses by
stable identity. A syntax-error tree must not abort extraction of the rest of
the project: the module remains visible and declarations outside erroneous
regions may be retained. The adapter never mutates caller input.

### TSA-007 - Python and non-script compatibility

Python extraction and ids remain unchanged. CSS and HTML remain observed `file`
nodes. `extract_python_graph` remains Python-only. `extract_project_graph`
dispatches only supported script suffixes to the new adapter.

### TSA-008 - Existing consumer integration

The richer nodes and relations must work without a second API:

- `/api/graph` and graph cache use `extract_project_graph` as today;
- `/api/source` remains the source authority;
- Explorer and Code navigate exact source lines;
- Flow aggregates `depends_on` and `calls` through its existing rules;
- graph search, neighborhood/path tools and Diagram Studio consume the same
  common graph.

`interface` and `type` receive explicit but class-adjacent visual treatment.

### TSA-009 - Dependency and deployment contract

Tree-sitter runtime and language wheels are normal Python dependencies. No npm,
Node parser process, vendored grammar, server subprocess or frontend bundler is
introduced. Supported version ranges are bounded in `pyproject.toml`.

## Acceptance scenarios

| ID | Expected result |
|---|---|
| TSA-A01 | JS functions/classes/methods replace the former file-only representation and open at exact source lines |
| TSA-A02 | TS interfaces, type aliases, enums, classes and typed methods appear with stable ids |
| TSA-A03 | JSX and TSX arrow components appear as functions without parsing JSX elements as calls |
| TSA-A04 | A relative ES import creates one module `depends_on` relation and imported calls target the correct declaration |
| TSA-A05 | A relative CommonJS require resolves to its observed module; a bare npm require creates no synthetic node |
| TSA-A06 | Dynamic/property calls without unique evidence create no `calls` relation |
| TSA-A07 | A malformed script does not prevent Python or other scripts from being extracted |
| TSA-A08 | Reversing script input order yields identical node and relation identities |
| TSA-A09 | Opening Graph Lab itself exposes symbols beneath `static/*.js` while CSS/HTML remain files |
| TSA-A10 | Existing Python, server, MCP and JavaScript regression suites remain green |

## Non-goals

- Full TypeScript type checking, `tsconfig` path aliases or project references.
- Package-manager dependency graphs or nodes for third-party packages.
- Points-to analysis, virtual dispatch, framework lifecycle or call ordering.
- Symbols declared only in object literals, closures or generated code.
- Editing/proposing TypeScript interfaces through the proposal form.
- Generalizing a language-plugin framework before a second semantic adapter
  exists.

## Completion boundary

Completion requires adapter fixtures, full regression suites, a smoke against
the live Graph Lab repository and a rendered browser check showing a script
module, one nested symbol and its exact code range. Endpoint counts alone are not
rendered acceptance evidence.
