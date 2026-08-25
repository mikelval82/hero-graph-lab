# TypeScript and JavaScript adapter traceability

| Requirement | Decisions | Planned implementation | Evidence | Status |
|---|---|---|---|---|
| TSA-001 | TSA-D001 | suffix-to-grammar parser selection | Pending | Specified |
| TSA-002 | TSA-D002, TSA-D007 | script module nodes and source ranges | Pending | Specified |
| TSA-003 | TSA-D003, TSA-D006 | declaration collector | Pending | Specified |
| TSA-004 | TSA-D003, TSA-D005 | relative module resolver | Pending | Specified |
| TSA-005 | TSA-D003, TSA-D004 | bounded call resolver | Pending | Specified |
| TSA-006 | TSA-D003, TSA-D004 | stable deduplication and error tolerance | Pending | Specified |
| TSA-007 | TSA-D002 | extractor dispatch and compatibility tests | Pending | Specified |
| TSA-008 | TSA-D005, TSA-D006, TSA-D007 | existing graph/UI consumers and small kind styling | Pending | Specified |
| TSA-009 | TSA-D001 | bounded Python dependencies | Pending | Specified |

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
