from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from hero_graph_lab.architecture.scenarios import ArchitectureScenarioService


def snapshot(*, description: str = "Compare alternatives.", include_walkthrough: bool = False):  # noqa: ANN201
    nodes = [
        {
            "id": "proposal:scenarios",
            "label": "ArchitectureScenarioService",
            "kind": "class",
            "parent": "observed:architecture",
            "status": "proposed",
            "description": description,
            "target_path": "src/hero_graph_lab/architecture/scenarios.py",
            "qualified_name": "ArchitectureScenarioService",
            "signature": "",
            "docstring": "Capture and compare immutable architecture alternatives.",
            "satisfies": ["AW-003"],
            "acceptance": ["Comparison reports exact contract changes."],
        }
    ]
    if include_walkthrough:
        nodes.append(
            {
                "id": "proposal:walkthrough",
                "label": "GuidedWalkthrough",
                "kind": "class",
                "parent": "observed:architecture",
                "status": "proposed",
                "description": "Explain the design in a deliberate order.",
                "target_path": "src/hero_graph_lab/architecture/walkthrough.py",
                "qualified_name": "GuidedWalkthrough",
                "signature": "",
                "docstring": "Build a reviewable guided tour.",
                "satisfies": ["AW-006"],
                "acceptance": ["Every step identifies its supporting graph node."],
            }
        )
    edges = [
        {
            "source": "proposal:scenarios",
            "target": "observed:server",
            "kind": "integrates_with",
            "label": "exposes scenario API",
            "status": "proposed",
            "properties": {"evidence": "server.py"},
        }
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "observed_endpoints": [
            {
                "id": "observed:architecture",
                "label": "architecture",
                "kind": "package",
                "source": "src/hero_graph_lab/architecture",
            },
            {
                "id": "observed:server",
                "label": "server.py",
                "kind": "module",
                "source": "src/hero_graph_lab/server.py",
            },
        ],
    }


class ArchitectureScenarioServiceTest(TestCase):
    def test_capture_is_immutable_normalized_and_durable(self) -> None:
        with TemporaryDirectory() as directory:
            state_path = Path(directory) / "scenarios.json"
            project = Path(directory) / "project"
            project.mkdir()
            service = ArchitectureScenarioService(state_path, lambda: project)
            draft = snapshot()

            captured = service.capture(
                {"name": "  Workbench A  ", "description": "  Baseline  ", "snapshot": draft}
            )
            draft["nodes"][0]["description"] = "Mutated after capture"
            reloaded = ArchitectureScenarioService(state_path, lambda: project).get(captured["id"])

            self.assertEqual(captured["name"], "Workbench A")
            self.assertEqual(captured["description"], "Baseline")
            self.assertEqual(
                reloaded["snapshot"]["nodes"][0]["description"],
                "Compare alternatives.",
            )
            self.assertEqual(reloaded["project"], str(project.resolve()))
            self.assertEqual(service.list()[0]["node_count"], 1)
            self.assertEqual(service.list()[0]["relation_count"], 1)

    def test_scenarios_are_partitioned_by_resolved_project(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            selected = [first]
            service = ArchitectureScenarioService(root / "scenarios.json", lambda: selected[0])

            first_scenario = service.capture({"name": "First", "snapshot": snapshot()})
            selected[0] = second
            second_scenario = service.capture({"name": "Second", "snapshot": snapshot()})

            self.assertEqual([item["id"] for item in service.list()], [second_scenario["id"]])
            with self.assertRaises(KeyError):
                service.get(first_scenario["id"])
            selected[0] = first
            self.assertEqual([item["id"] for item in service.list()], [first_scenario["id"]])

    def test_compare_reports_field_node_and_acceptance_changes_in_both_directions(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            project.mkdir()
            service = ArchitectureScenarioService(
                Path(directory) / "scenarios.json", lambda: project
            )
            left = service.capture({"name": "A", "snapshot": snapshot()})
            changed = snapshot(
                description="Compare alternatives without mutating the active draft.",
                include_walkthrough=True,
            )
            changed["nodes"][0]["acceptance"].append("Comparison is reversible.")
            right = service.capture({"name": "B", "snapshot": changed})

            forward = service.compare(left["id"], right["id"])
            reverse = service.compare(right["id"], left["id"])

            self.assertEqual(forward["summary"]["added_nodes"], 1)
            self.assertEqual(forward["added_nodes"][0]["id"], "proposal:walkthrough")
            self.assertEqual(
                forward["changed_nodes"][0]["changes"]["description"],
                {
                    "before": "Compare alternatives.",
                    "after": "Compare alternatives without mutating the active draft.",
                },
            )
            self.assertIn(
                {"node_id": "proposal:scenarios", "criterion": "Comparison is reversible."},
                forward["acceptance_added"],
            )
            self.assertEqual(reverse["summary"]["removed_nodes"], 1)
            self.assertEqual(reverse["removed_nodes"][0]["id"], "proposal:walkthrough")
            self.assertIn(
                {"node_id": "proposal:scenarios", "criterion": "Comparison is reversible."},
                reverse["acceptance_removed"],
            )

    def test_invalid_capture_does_not_corrupt_existing_document(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            project.mkdir()
            state_path = Path(directory) / "scenarios.json"
            service = ArchitectureScenarioService(state_path, lambda: project)
            existing = service.capture({"name": "Valid", "snapshot": snapshot()})
            before = state_path.read_text(encoding="utf-8")
            malformed = snapshot()
            malformed["edges"][0]["target"] = "missing:endpoint"

            with self.assertRaisesRegex(ValueError, "unknown endpoint"):
                service.capture({"name": "Invalid", "snapshot": malformed})

            self.assertEqual(state_path.read_text(encoding="utf-8"), before)
            self.assertEqual(service.get(existing["id"])["name"], "Valid")
            self.assertEqual(json.loads(before)["version"], 1)


if __name__ == "__main__":
    import unittest

    unittest.main()
