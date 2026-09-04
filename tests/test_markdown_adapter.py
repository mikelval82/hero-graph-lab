from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from hero_graph_lab.markdown_adapter import MarkdownGraphAdapter, MarkdownSource


class MarkdownGraphAdapterTest(TestCase):
    def _source(self, directory: Path, content: str, name: str = "README.md") -> MarkdownSource:
        path = directory / name
        path.write_text(content, encoding="utf-8")
        return MarkdownSource(path, name, "package:project", name)

    def test_creates_document_and_contains_edge(self) -> None:
        with TemporaryDirectory() as directory:
            source = self._source(Path(directory), "# Guide\n")

            graph = MarkdownGraphAdapter().extract([source])

        self.assertEqual(graph["nodes"], [{
            "id": "document:README.md",
            "kind": "document",
            "label": "README.md",
            "parent": "package:project",
            "line": 1,
            "end_line": 1,
            "source": "README.md",
        }])
        self.assertEqual(graph["edges"], [{
            "source": "package:project",
            "target": "document:README.md",
            "kind": "contains",
        }])

    def test_resolves_unique_inline_and_link_references(self) -> None:
        with TemporaryDirectory() as directory:
            source = self._source(
                Path(directory),
                "Use `MarkdownGraphAdapter` and [the extractor](src/extractor.py).\n",
            )
            observed = [
                {"id": "class:MarkdownGraphAdapter", "label": "MarkdownGraphAdapter"},
                {"id": "module:src/extractor.py", "source": "src/extractor.py", "kind": "module"},
            ]

            graph = MarkdownGraphAdapter().extract([source], observed)

        self.assertEqual(
            graph["edges"],
            [
                {"source": "document:README.md", "target": "class:MarkdownGraphAdapter", "kind": "references"},
                {"source": "document:README.md", "target": "module:src/extractor.py", "kind": "references"},
                {"source": "package:project", "target": "document:README.md", "kind": "contains"},
            ],
        )

    def test_does_not_invent_or_ambiguously_resolve_targets(self) -> None:
        with TemporaryDirectory() as directory:
            source = self._source(Path(directory), "`Missing` `Shared`\n")
            observed = [
                {"id": "class:First.Shared", "label": "Shared"},
                {"id": "class:Second.Shared", "label": "Shared"},
            ]

            graph = MarkdownGraphAdapter().extract([source], observed)

        self.assertEqual(
            graph["edges"],
            [{"source": "package:project", "target": "document:README.md", "kind": "contains"}],
        )

    def test_ignores_fenced_and_indented_code(self) -> None:
        with TemporaryDirectory() as directory:
            source = self._source(
                Path(directory),
                "```python\n`Hidden`\n```\n\n    `AlsoHidden`\n\nVisible: `Observed`.\n",
            )
            observed = [{"id": "class:Observed", "label": "Observed"}, {"id": "class:Hidden", "label": "Hidden"}]

            graph = MarkdownGraphAdapter().extract([source], observed)

        self.assertIn(
            {"source": "document:README.md", "target": "class:Observed", "kind": "references"},
            graph["edges"],
        )
        self.assertNotIn(
            {"source": "document:README.md", "target": "class:Hidden", "kind": "references"},
            graph["edges"],
        )

