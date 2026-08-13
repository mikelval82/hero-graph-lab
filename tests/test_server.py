from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import os

from hero_graph_lab.explore.clients import load_project_env
from hero_graph_lab.explore.models import ModelRequest, ModelResponse
from hero_graph_lab.server import LabState, initial_project, make_handler


FIXTURE = Path(__file__).parents[1] / "fixtures" / "order_app"


class LabServerTest(TestCase):
    def test_when_explore_provider_fails_expect_json_bad_gateway(self) -> None:
        class FailingModelClient:
            provider = "gemini"
            model = "gemini-2.5-flash"

            def complete(self, request: ModelRequest) -> ModelResponse:
                del request
                raise RuntimeError("Gemini request failed: 429 RESOURCE_EXHAUSTED")

        with TemporaryDirectory() as directory:
            state = LabState(
                FIXTURE,
                Path(directory) / "observations.json",
                explore_client=FailingModelClient(),
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                create = Request(f"{base_url}/api/explore/sessions", data=b"", method="POST")
                with urlopen(create) as response:
                    session = json.load(response)
                message = Request(
                    f"{base_url}/api/explore/sessions/{session['id']}/messages",
                    data=json.dumps({"message": "Hello", "context": {}}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )

                with self.assertRaises(HTTPError) as raised:
                    urlopen(message)

                self.assertEqual(raised.exception.code, 502)
                self.assertEqual(
                    json.load(raised.exception),
                    {"error": "Gemini request failed: 429 RESOURCE_EXHAUSTED"},
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_mission_project_replaces_fixture_for_initial_graph(self) -> None:
        with TemporaryDirectory() as directory:
            selected = Path(directory)

            project = initial_project(FIXTURE, selected)

            self.assertTrue(project.samefile(selected))

    def test_serves_graph_and_persists_feedback(self) -> None:
        with TemporaryDirectory() as directory:
            state_path = Path(directory) / "observations.json"
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                make_handler(LabState(FIXTURE, state_path)),
            )
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                with urlopen(f"{base_url}/api/graph") as response:
                    graph = json.load(response)
                self.assertEqual(graph["source"], "order_app")
                self.assertEqual(graph["root"], "package:order_app")

                with urlopen(f"{base_url}/api/source") as response:
                    source = json.load(response)
                self.assertEqual(source["source"], "order_app")
                self.assertEqual(len(source["sources"]), 6)
                self.assertIn(
                    "def place(self, order: Order) -> str:",
                    source["sources"]["application/order_service.py"]["content"],
                )

                with urlopen(base_url) as response:
                    index = response.read().decode("utf-8")
                self.assertIn("Graph Lab", index)
                self.assertIn('id="file-tree"', index)
                self.assertIn('id="trace-calls"', index)
                self.assertIn('id="graph-viewport"', index)
                self.assertIn('id="zoom-in"', index)
                self.assertIn('id="zoom-fit"', index)
                self.assertIn('id="lock-layout"', index)
                self.assertEqual(index.count("data-collapse-panel="), 3)
                self.assertIn('data-collapse-panel="explorer"', index)
                self.assertIn('data-collapse-panel="code"', index)
                self.assertIn('data-collapse-panel="inspector"', index)
                self.assertEqual(index.count("data-graph-view="), 3)
                self.assertIn('data-graph-view="structure"', index)
                self.assertIn('data-graph-view="focus"', index)
                self.assertEqual(index.count("data-inspector-tab="), 2)
                self.assertNotIn('data-inspector-tab="selection"', index)
                self.assertNotIn('id="selection-panel"', index)
                self.assertNotIn('id="open-scope"', index)
                self.assertIn('id="mission-dialog"', index)
                self.assertIn('id="project-open"', index)
                self.assertIn('id="mission-documents"', index)
                self.assertIn('id="chat-messages"', index)
                self.assertIn('data-chat-mode="explore"', index)
                self.assertIn('data-chat-mode="mission"', index)
                self.assertIn('id="explore-context"', index)
                self.assertIn('id="explore-pins"', index)
                self.assertIn('id="chat-microphone"', index)
                self.assertIn('id="chat-speech"', index)
                self.assertIn('id="shortcut-dialog"', index)
                self.assertIn('id="command-palette-dialog"', index)
                self.assertIn('id="diagram-dialog"', index)
                self.assertIn('id="project-node"', index)
                self.assertIn('data-command="selection.project"', index)
                self.assertIn('id="graph-projection-bar"', index)
                self.assertIn('id="graph-projection-back"', index)
                self.assertIn('id="graph-projection-restore"', index)
                self.assertIn('id="diagram-type"', index)
                self.assertIn('id="diagram-depth"', index)
                self.assertIn('id="diagram-path-from"', index)
                self.assertIn('id="diagram-path-to"', index)
                self.assertIn('id="diagram-confidence"', index)
                self.assertIn('data-command="selection.explain"', index)
                self.assertIn('data-command="calls.trace"', index)
                self.assertIn('data-command="selection.pin"', index)
                self.assertEqual(index.count('data-font-panel='), 4)
                self.assertIn('id="document-preview"', index)
                self.assertIn('id="code-search-input"', index)
                self.assertIn('id="code-search-next"', index)
                self.assertIn('data-document-mode="preview"', index)
                self.assertIn("mermaid@11.6.0", index)
                self.assertIn("dompurify@3.2.6", index)
                self.assertIn('src="/mission.js"', index)
                self.assertIn('src="/explore.js"', index)
                self.assertIn('src="/rich-render.js"', index)
                self.assertIn('src="/diagrams.js"', index)
                self.assertIn('src="/commands.js"', index)
                self.assertLess(index.index('src="/rich-render.js"'), index.index('src="/mission.js"'))
                self.assertLess(index.index('src="/explore.js"'), index.index('src="/diagrams.js"'))
                self.assertLess(index.index('src="/diagrams.js"'), index.index('src="/commands.js"'))
                self.assertLess(index.index('id="project-open"'), index.index('class="mission-presence"'))
                self.assertLess(index.index('class="graph-toolbar"'), index.index('class="design-tools"'))
                self.assertNotIn('class="project-panel" aria-labelledby="design-tools-title"', index)
                self.assertEqual(index.count('role="separator"'), 3)
                self.assertNotIn(">Topology<", index)
                self.assertNotIn(">Hybrid<", index)
                self.assertEqual(index.count("<!doctype html>"), 1)

                with urlopen(f"{base_url}/mission.js") as response:
                    mission_script = response.read().decode("utf-8")
                with urlopen(f"{base_url}/explore.js") as response:
                    explore_script = response.read().decode("utf-8")
                with urlopen(f"{base_url}/app.js") as response:
                    app_script = response.read().decode("utf-8")
                with urlopen(f"{base_url}/rich-render.js") as response:
                    rich_render_script = response.read().decode("utf-8")
                with urlopen(f"{base_url}/commands.js") as response:
                    commands_script = response.read().decode("utf-8")
                with urlopen(f"{base_url}/diagrams.js") as response:
                    diagrams_script = response.read().decode("utf-8")
                with urlopen(f"{base_url}/graph-render.js") as response:
                    graph_script = response.read().decode("utf-8")
                with urlopen(f"{base_url}/styles.css") as response:
                    styles = response.read().decode("utf-8")
                self.assertIn("function renderJsonPreview", mission_script)
                self.assertIn("function renderTaskWorkplan", mission_script)
                self.assertIn("function appendDocumentGroup", mission_script)
                self.assertIn("agent_progress", mission_script)
                self.assertIn("function activityMetrics", mission_script)
                self.assertIn("function selectLocalProject", mission_script)
                self.assertIn("function currentExploreContext", explore_script)
                self.assertIn("function renderPinnedNodes", explore_script)
                self.assertIn("pinnedNodeIds", explore_script)
                self.assertIn("BrowserSpeechRecognition", explore_script)
                self.assertIn("SpeechSynthesisUtterance", explore_script)
                self.assertIn("RichContentRenderer.render", explore_script)
                self.assertIn("function submitExplorePrompt", explore_script)
                self.assertIn("submitExplorePrompt(text, context = currentExploreContext())", explore_script)
                self.assertIn('if (message.role === "user") body.textContent = message.content', explore_script)
                self.assertIn('securityLevel: "strict"', rich_render_script)
                self.assertIn("DOMPurify.sanitize(parsed", rich_render_script)
                self.assertIn("USE_PROFILES: { svg: true, svgFilters: true }", rich_render_script)
                self.assertIn("Diagram could not be rendered", rich_render_script)
                self.assertIn("RichContentRenderer.render(preview", mission_script)
                self.assertIn('id: "selection.explain"', commands_script)
                self.assertIn('id: "selection.diagram"', commands_script)
                self.assertIn('id: "selection.project"', commands_script)
                self.assertIn('g: "selection.project"', commands_script)
                self.assertIn('id: "relation.add"', commands_script)
                self.assertIn("function editableTarget", commands_script)
                self.assertIn("function graphHasFocus", commands_script)
                self.assertIn("responsabilidad del elemento", commands_script)
                self.assertIn("HeroDiagrams.open()", commands_script)
                self.assertIn("function hierarchyDiagram", diagrams_script)
                self.assertIn("function classDiagram", diagrams_script)
                self.assertIn("function callDiagram", diagrams_script)
                self.assertIn("function moduleDiagram", diagrams_script)
                self.assertIn("function neighborhoodDiagram", diagrams_script)
                self.assertIn("function pathDiagram", diagrams_script)
                self.assertIn("function inferredSequence", diagrams_script)
                self.assertIn('label: "Business sequence (INFERRED)"', diagrams_script)
                self.assertIn("The AST graph does not preserve call order", diagrams_script)
                self.assertIn("function compactInferenceContext", diagrams_script)
                self.assertIn("visibleNodeIds: [...visibleIds].slice", diagrams_script)
                self.assertIn("function graphSignature", diagrams_script)
                self.assertIn("function recommendedProjection", diagrams_script)
                self.assertIn("function activateProjection", diagrams_script)
                self.assertIn("function expandProjection", diagrams_script)
                self.assertIn("function backProjection", diagrams_script)
                self.assertIn("function restoreProjection", diagrams_script)
                self.assertIn("function mergeProjectionGraphs", diagrams_script)
                self.assertIn("G, E, or double-click", diagrams_script)
                self.assertIn("promptVersion: 1", diagrams_script)
                self.assertEqual(diagrams_script.count("deterministic: true"), 6)
                self.assertEqual(diagrams_script.count("deterministic: false"), 1)
                self.assertNotIn('addEventListener("click", toggleCallTrace)', app_script)
                self.assertIn('retry: { endpoint: "retry-review"', mission_script)
                self.assertIn("function rebuildGraphIndexes", app_script)
                self.assertIn("state.childrenByParent.get(scopeId)", app_script)
                self.assertIn("function structureGraph", app_script)
                self.assertIn("function focusGraph", app_script)
                self.assertIn("function navigateGraphBack", app_script)
                self.assertIn("function callTraceGraph", app_script)
                self.assertIn("if (state.callTrace) return callTraceGraph();", app_script)
                self.assertIn("if (state.graphProjection) return state.graphProjection.graph;", app_script)
                self.assertIn("HeroDiagrams?.expandProjection(completedDrag.nodeId)", app_script)
                self.assertIn('projectionActive ? "Expand node" : "Expand"', app_script)
                self.assertIn("trace.returnView = {", app_script)
                self.assertIn("clearCallTrace({ restoreViewport: true })", app_script)
                self.assertIn("Previous view restored", app_script)
                self.assertIn('state.callTrace ? "Restore view" : "Trace calls"', app_script)
                self.assertIn("flowGraph(expandedNodes)", app_script)
                self.assertIn("function flowJourneyGraph", app_script)
                self.assertIn("function flowTrailTo", app_script)
                self.assertIn("return flowJourneyGraph()", app_script)
                self.assertIn("updateGraphSelectionStyles", graph_script)
                self.assertIn("state.graphProjection?.savedLayout", graph_script)
                self.assertIn("!state.graphProjection", graph_script)
                self.assertIn("function setGraphView", app_script)
                self.assertIn("function captureGraphViewState", app_script)
                self.assertIn("function graphProjectionKey", app_script)
                self.assertIn("state.viewStates[state.view]", app_script)
                self.assertIn('if (state.view === "focus") return;', app_script)
                self.assertIn("function setGraphZoom", app_script)
                self.assertIn("const fittedScale = Math.min(availableWidth / state.graphWidth, availableHeight / state.graphHeight)", app_script)
                stop_drag_script = app_script[app_script.index("function stopDrag"):app_script.index("function setSelection")]
                expand_index = stop_drag_script.index("if (canEnterScope(completedDrag.nodeId)) expandSelectedNode();")
                self.assertGreater(stop_drag_script.index("fitGraphToView();"), expand_index)
                self.assertIn("GRAPH_FIT_PADDING", app_script)
                self.assertIn("function startGraphPan", app_script)
                self.assertIn("function toggleGraphLayoutLock", app_script)
                self.assertIn("if (state.layoutLocked && state.layoutSnapshot) return state.layoutSnapshot.graph", app_script)
                self.assertIn("function updateCodeSearch", app_script)
                self.assertIn("function initializePanelTypography", app_script)
                self.assertIn("hero-graph-lab-typography-v1", app_script)
                self.assertIn('addEventListener("mission-document-opened"', app_script)
                self.assertIn('new Set(panelLayout.collapsed)', app_script)
                self.assertIn("state.treeExpanded = new Set(state.graph.root ? [state.graph.root] : []);", app_script)
                self.assertIn("function selectionDimmingActive", graph_script)
                self.assertIn('!state.graphProjection && state.view !== "structure"', graph_script)
                self.assertIn("activeAnchor: state.selected", diagrams_script)
                self.assertIn("selected: projection.activeAnchor", diagrams_script)
                self.assertIn("function focusLayout", graph_script)
                self.assertIn("function structureLayout", graph_script)
                self.assertIn("function graphNodeMetrics", graph_script)
                self.assertIn("function relationLabelOffsets", graph_script)
                self.assertIn("const scale = graphTextScale()", graph_script)
                self.assertIn('visualRole = role === "human" || role === "user"', mission_script)
                self.assertIn(".chat-message.human { align-self: flex-end", styles)
                self.assertIn(".chat-message.agent { align-self: flex-start", styles)
                self.assertIn(".scope-crumb.trail-crumb", styles)
                self.assertIn(".workplan-list", styles)
                self.assertIn(".document-group-list", styles)
                self.assertIn(".activity-agent_progress", styles)
                self.assertIn("--accent: #176b57", styles)
                self.assertIn(".panel-kicker { color: var(--graph-accent)", styles)
                self.assertIn("border-bottom: 4px solid var(--accent)", styles)
                self.assertNotIn(".panel-kicker { color: var(--class)", styles)

                payload = json.dumps(
                    {
                        "view": "flow",
                        "task": "follow pricing",
                        "friction": 2,
                        "decision": "change",
                        "notes": "The direction was clear.",
                    }
                ).encode("utf-8")
                request = Request(
                    f"{base_url}/api/observations",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request) as response:
                    observation = json.load(response)

                self.assertEqual(observation["view"], "flow")
                persisted = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertEqual(persisted["observations"], [observation])
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_loads_project_env_for_gemini_provider(self) -> None:
        previous = os.environ.get("GOOGLE_API_KEY")
        os.environ.pop("GOOGLE_API_KEY", None)
        try:
            with TemporaryDirectory() as directory:
                temp_dir = Path(directory)
                env_path = temp_dir / ".env"
                env_path.write_text("GOOGLE_API_KEY=test-google-key\n", encoding="utf-8")
                load_project_env(temp_dir)
                self.assertEqual(os.environ["GOOGLE_API_KEY"], "test-google-key")
        finally:
            if previous is None:
                os.environ.pop("GOOGLE_API_KEY", None)
            else:
                os.environ["GOOGLE_API_KEY"] = previous

    def test_explore_session_lifecycle(self) -> None:
        with TemporaryDirectory() as directory:
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                make_handler(LabState(FIXTURE, Path(directory) / "observations.json")),
            )
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                with urlopen(f"{base_url}/api/explore/status") as response:
                    status = json.load(response)
                self.assertEqual(status["provider"], "fake")

                create = Request(f"{base_url}/api/explore/sessions", data=b"", method="POST")
                with urlopen(create) as response:
                    session = json.load(response)
                self.assertEqual(response.status, 201)

                message = Request(
                    f"{base_url}/api/explore/sessions/{session['id']}/messages",
                    data=json.dumps({"message": "What is selected?", "context": {}}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(message) as response:
                    answered = json.load(response)
                self.assertEqual([item["role"] for item in answered["messages"]], ["user", "assistant"])
                self.assertIn("proveedor determinista", answered["messages"][1]["content"])

                with urlopen(f"{base_url}/api/explore/sessions/{session['id']}") as response:
                    restored = json.load(response)
                self.assertEqual(restored["messages"], answered["messages"])

                delete = Request(f"{base_url}/api/explore/sessions/{session['id']}", method="DELETE")
                with urlopen(delete) as response:
                    self.assertEqual(json.load(response), {"deleted": True})
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_proxies_harness_without_exposing_worker_credentials(self) -> None:
        class FakeHarnessHost:
            def __init__(self) -> None:
                self.requests: list[tuple[str, str, bytes | None]] = []

            def status(self) -> dict[str, object]:
                return {"configured": True, "running": True, "mission_id": "sample:graph-lab"}

            def start(self, **options) -> dict[str, object]:  # noqa: ANN003
                return self.status()

            def configure_project(self, project_dir: Path) -> dict[str, object]:
                self.project_dir = project_dir
                return self.status()

            def stop(self) -> None:
                return None

            def request(self, method: str, path: str, body: bytes | None = None):  # noqa: ANN201
                self.requests.append((method, path, body))
                return 200, "application/json", json.dumps({"api_version": "v1"}).encode()

        with TemporaryDirectory() as directory:
            host = FakeHarnessHost()
            state = LabState(FIXTURE, Path(directory) / "observations.json", host)
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                make_handler(state),
            )
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                with urlopen(f"{base_url}/api/harness/status") as response:
                    status = json.load(response)
                selected_project = Path(directory) / "selected"
                selected_project.mkdir()
                state.directory_selector = lambda initial: selected_project
                select_request = Request(
                    f"{base_url}/api/project/select",
                    data=b"",
                    method="POST",
                )
                with urlopen(select_request) as response:
                    selected = json.load(response)
                request = Request(
                    f"{base_url}/api/harness/v1/actions/research",
                    data=json.dumps({"expected_session_revision": 1}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request) as response:
                    proxied = json.load(response)

                self.assertTrue(status["running"])
                self.assertTrue(selected["project_selected"])
                self.assertTrue(host.project_dir.samefile(selected_project))
                self.assertEqual(proxied["api_version"], "v1")
                self.assertEqual(host.requests[0][0:2], ("POST", "/api/v1/actions/research"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == "__main__":
    import unittest

    unittest.main()
