# Project source graph traceability

| Requirement | Decisions | Implementation | Automated evidence | Rendered evidence | Status |
|---|---|---|---|---|---|
| PSG-001 | PSG-D002, PSG-D004 | `extractor.project_source_files` | Pending | N/A | Specified |
| PSG-002 | PSG-D001, PSG-D003, PSG-D005 | Project graph file nodes | Pending | PSG-A01, PSG-A03 pending | Specified |
| PSG-003 | PSG-D004 | `LabState._source_fingerprint`, `LabState.source` | Pending | PSG-A02 pending | Specified |
| PSG-004 | PSG-D003 | Compatibility wrappers and Python suite | Pending | N/A | Specified |
| PSG-005 | PSG-D001, PSG-D005 | Existing proposal connection derivation | Pending | PSG-A05 pending | Specified |

## Baseline evidence - 2026-08-25

- Graph Lab commit: `3b66bc0`; worktree clean.
- `python_source_files` filters exclusively on `.py`.
- `LabState.source` and `_source_fingerprint` both call
  `python_source_files`.
- `LabState.graph` calls `extract_python_graph`.
- Live `GraphSearch` returned no nodes for `diagrams` or `projection`, although
  those files exist in `src/hero_graph_lab/static`.
- The regenerated Architecture Workbench is intentionally blocked from using
  fabricated anchors until PSG-001 through PSG-003 are implemented.
