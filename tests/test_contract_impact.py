from copy import deepcopy
from unittest import TestCase

from hero_graph_lab.architecture.impact import ContractImpactAnalyzer


PROVIDER_ID = "module:demo.provider"
CONSUMER_ID = "module:demo.consumer"
ENTRYPOINT_ID = "module:demo.entrypoint"
SIBLING_ID = "module:demo.sibling"


def snapshot(*, signature: str = "(baseline)", stale_anchor: bool = False):  # noqa: ANN201
    anchor_id = "module:demo.missing" if stale_anchor else PROVIDER_ID
    return {
        "nodes": [
            {
                "id": "proposal:workbench",
                "label": "Architecture Workbench",
                "kind": "package",
                "parent": None,
                "status": "proposed",
                "description": "Architecture tools.",
                "target_path": "src/demo/architecture",
                "qualified_name": "demo.architecture",
                "signature": "",
                "docstring": "Architecture tools.",
                "satisfies": ["AW-001"],
                "acceptance": ["Capabilities remain independent."],
            },
            {
                "id": "proposal:impact-module",
                "label": "impact.py",
                "kind": "module",
                "parent": "proposal:workbench",
                "status": "proposed",
                "description": "Explain change impact.",
                "target_path": "src/demo/architecture/impact.py",
                "qualified_name": "demo.architecture.impact",
                "signature": "",
                "docstring": "Explain change impact.",
                "satisfies": ["CI-001"],
                "acceptance": ["Every impact has evidence."],
            },
            {
                "id": "proposal:analyzer",
                "label": "ContractImpactAnalyzer",
                "kind": "class",
                "parent": "proposal:impact-module",
                "status": "proposed",
                "description": "Analyze normalized contracts.",
                "target_path": "src/demo/architecture/impact.py",
                "qualified_name": "demo.architecture.impact.ContractImpactAnalyzer",
                "signature": "",
                "docstring": "Analyze normalized contracts.",
                "satisfies": ["CI-001"],
                "acceptance": ["Analysis is deterministic."],
            },
            {
                "id": "proposal:analyze",
                "label": "analyze",
                "kind": "method",
                "parent": "proposal:analyzer",
                "status": "proposed",
                "description": "Compare a baseline and candidate.",
                "target_path": "src/demo/architecture/impact.py",
                "qualified_name": "demo.architecture.impact.ContractImpactAnalyzer.analyze",
                "signature": signature,
                "docstring": "Return drift and evidence-backed code impact.",
                "satisfies": ["CI-001"],
                "acceptance": ["Analysis is deterministic."],
            },
            {
                "id": "proposal:sibling-module",
                "label": "walkthrough.py",
                "kind": "module",
                "parent": "proposal:workbench",
                "status": "proposed",
                "description": "Explain a graph path.",
                "target_path": "src/demo/architecture/walkthrough.py",
                "qualified_name": "demo.architecture.walkthrough",
                "signature": "",
                "docstring": "Explain a graph path.",
                "satisfies": ["AW-006"],
                "acceptance": ["Steps retain evidence."],
            },
        ],
        "edges": [
            {
                "source": "proposal:impact-module",
                "target": anchor_id,
                "kind": "integrates_with",
                "label": "analyzes current graph",
                "status": "proposed",
                "properties": {},
            },
            {
                "source": "proposal:sibling-module",
                "target": SIBLING_ID,
                "kind": "integrates_with",
                "label": "reads graph path",
                "status": "proposed",
                "properties": {},
            },
        ],
        "observed_endpoints": [
            {"id": anchor_id, "label": "provider.py", "kind": "module", "source": "src/demo/provider.py"},
            {"id": SIBLING_ID, "label": "sibling.py", "kind": "module", "source": "src/demo/sibling.py"},
        ],
    }


def observed_graph():  # noqa: ANN201
    return {
        "nodes": [
            {"id": PROVIDER_ID, "label": "provider.py", "kind": "module", "source": "src/demo/provider.py"},
            {"id": CONSUMER_ID, "label": "consumer.py", "kind": "module", "source": "src/demo/consumer.py"},
            {"id": ENTRYPOINT_ID, "label": "entrypoint.py", "kind": "module", "source": "src/demo/entrypoint.py"},
            {"id": SIBLING_ID, "label": "sibling.py", "kind": "module", "source": "src/demo/sibling.py"},
            {"id": "module:demo.outgoing", "label": "outgoing.py", "kind": "module", "source": "src/demo/outgoing.py"},
            {"id": "package:demo", "label": "demo", "kind": "package", "source": "src/demo"},
        ],
        "edges": [
            {"source": CONSUMER_ID, "target": PROVIDER_ID, "kind": "depends_on"},
            {"source": ENTRYPOINT_ID, "target": CONSUMER_ID, "kind": "depends_on"},
            {"source": PROVIDER_ID, "target": "module:demo.outgoing", "kind": "depends_on"},
            {"source": "package:demo", "target": PROVIDER_ID, "kind": "contains"},
            {"source": SIBLING_ID, "target": PROVIDER_ID, "kind": "custom"},
        ],
    }


class ContractImpactAnalyzerTest(TestCase):
    def test_changed_child_uses_nearest_module_anchor_and_exact_incoming_paths(self) -> None:
        baseline = snapshot()
        candidate = snapshot(signature="(baseline, candidate, graph)")

        result = ContractImpactAnalyzer().analyze(baseline, candidate, observed_graph())

        self.assertEqual(result["summary"]["changed_contract_nodes"], 1)
        self.assertEqual([item["id"] for item in result["anchors"]], [PROVIDER_ID])
        self.assertEqual(result["anchors"][0]["contract_node_ids"], ["proposal:analyze"])
        self.assertEqual(
            [(item["id"], item["distance"]) for item in result["dependents"]],
            [(CONSUMER_ID, 1), (ENTRYPOINT_ID, 2)],
        )
        self.assertEqual(
            result["dependents"][1]["path"],
            [
                {"source": CONSUMER_ID, "target": PROVIDER_ID, "kind": "depends_on"},
                {"source": ENTRYPOINT_ID, "target": CONSUMER_ID, "kind": "depends_on"},
            ],
        )
        self.assertNotIn(SIBLING_ID, {item["id"] for item in result["anchors"]})
        self.assertNotIn("module:demo.outgoing", {item["id"] for item in result["dependents"]})

    def test_stale_anchor_is_reported_without_guessing_code_impact(self) -> None:
        baseline = snapshot(stale_anchor=True)
        candidate = snapshot(signature="(baseline, candidate, graph)", stale_anchor=True)

        result = ContractImpactAnalyzer().analyze(baseline, candidate, observed_graph())

        self.assertEqual(result["anchors"], [])
        self.assertEqual(result["dependents"], [])
        self.assertEqual(
            result["unresolved"],
            [{"contract_node_id": "proposal:analyze", "reason": "stale_observed_anchor"}],
        )

    def test_unchanged_contract_has_no_impact_and_inputs_remain_immutable(self) -> None:
        baseline = snapshot()
        candidate = snapshot()
        graph = observed_graph()
        originals = deepcopy((baseline, candidate, graph))

        first = ContractImpactAnalyzer().analyze(baseline, candidate, graph)
        second = ContractImpactAnalyzer().analyze(
            baseline,
            candidate,
            {"nodes": list(reversed(graph["nodes"])), "edges": list(reversed(graph["edges"]))},
        )

        self.assertEqual(first, second)
        self.assertEqual(first["summary"]["changed_contract_nodes"], 0)
        self.assertEqual(first["anchors"], [])
        self.assertEqual((baseline, candidate, graph), originals)

    def test_explicit_bounds_report_truncated_analysis(self) -> None:
        candidate = snapshot(signature="(baseline, candidate, graph)")

        result = ContractImpactAnalyzer(max_depth=1, max_dependents=1).analyze(
            snapshot(), candidate, observed_graph()
        )

        self.assertEqual([item["id"] for item in result["dependents"]], [CONSUMER_ID])
        self.assertTrue(result["summary"]["truncated"])


if __name__ == "__main__":
    import unittest

    unittest.main()

