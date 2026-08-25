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
    def test_scenario_api_captures_lists_retrieves_and_compares_project_drafts(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            state = LabState(project, root / "observations.json")
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            snapshot = {
                "nodes": [
                    {
                        "id": "proposal:scenario",
                        "label": "ArchitectureScenarioService",
                        "kind": "class",
                        "parent": "observed:server",
                        "status": "proposed",
                        "description": "Compare immutable alternatives.",
                        "target_path": "src/hero_graph_lab/architecture/scenarios.py",
                        "qualified_name": "ArchitectureScenarioService",
                        "signature": "",
                        "docstring": "Compare architecture alternatives.",
                        "satisfies": ["AW-003"],
                        "acceptance": ["Reports exact changes."],
                    }
                ],
                "edges": [],
                "observed_endpoints": [
                    {
                        "id": "observed:server",
                        "label": "server.py",
                        "kind": "module",
                        "source": "src/hero_graph_lab/server.py",
                    }
                ],
            }
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"

                def post(path: str, body: dict):  # noqa: ANN202
                    request = Request(
                        f"{base_url}{path}",
                        data=json.dumps(body).encode(),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urlopen(request) as response:
                        return response.status, json.load(response)

                status, left = post(
                    "/api/scenarios", {"name": "A", "snapshot": snapshot}
                )
                changed = json.loads(json.dumps(snapshot))
                changed["nodes"][0]["description"] = "Compare exact contract alternatives."
                _, right = post("/api/scenarios", {"name": "B", "snapshot": changed})

                with urlopen(f"{base_url}/api/scenarios") as response:
                    listed = json.load(response)
                with urlopen(f"{base_url}/api/scenarios/{left['id']}") as response:
                    retrieved = json.load(response)
                _, comparison = post(
                    "/api/scenarios/compare",
                    {"left_id": left["id"], "right_id": right["id"]},
                )

                self.assertEqual(status, 201)
                self.assertEqual([item["name"] for item in listed["scenarios"]], ["A", "B"])
                self.assertEqual(retrieved["id"], left["id"])
                self.assertEqual(comparison["summary"]["changed_nodes"], 1)

                with self.assertRaises(HTTPError) as raised:
                    post(
                        "/api/scenarios",
                        {"name": "Broken", "snapshot": {"nodes": [], "edges": []}},
                    )
                self.assertEqual(raised.exception.code, 400)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_web_source_nodes_and_source_delivery_share_the_cache_boundary(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            static = project / "static"
            static.mkdir(parents=True)
            (project / "service.py").write_text("def run():\n    return True\n", encoding="utf-8")
            script = static / "app.js"
            script.write_text("export const version = 1;\n", encoding="utf-8")
            state = LabState(project, Path(directory) / "observations.json")

            first_graph = state.graph()
            first_source = state.source()
            script.write_text(
                "export const version = 2;\nexport const ready = true;\n",
                encoding="utf-8",
            )
            second_graph = state.graph()
            second_source = state.source()

        file_node = next(
            node for node in second_graph["nodes"] if node["source"] == "static/app.js"
        )
        self.assertEqual(file_node["kind"], "file")
        self.assertEqual(file_node["end_line"], 2)
        self.assertIn("static/app.js", first_source["sources"])
        self.assertIn("version = 2", second_source["sources"]["static/app.js"]["content"])
        self.assertIsNot(first_graph, second_graph)

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

    def test_graph_cache_refreshes_when_project_sources_change(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            existing = project / "existing.py"
            existing.write_text("VALUE = 1\n", encoding="utf-8")
            state = LabState(project, project / "observations.json")

            initial = state.graph()
            created = project / "notification_gateway.py"
            created.write_text(
                "class NotificationGateway:\n"
                "    def send_notification(self, chat_id: str, text: str) -> bool:\n"
                "        return True\n",
                encoding="utf-8",
            )
            refreshed = state.graph()

            self.assertEqual(len(initial["nodes"]), 2)
            self.assertTrue(
                any(node["label"] == "NotificationGateway" for node in refreshed["nodes"])
            )
            self.assertTrue(
                any(node["label"] == "send_notification" for node in refreshed["nodes"])
            )

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
                self.assertIn('id="project-dialog"', index)
                self.assertIn('id="project-form"', index)
                self.assertIn('id="project-path"', index)
                self.assertIn('id="open-scenarios"', index)
                self.assertIn('id="scenario-dialog"', index)
                self.assertIn('id="scenario-capture-form"', index)
                self.assertIn('id="scenario-result"', index)
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
                self.assertIn('id="mission-contracts"', index)
                self.assertIn('id="chat-messages"', index)
                self.assertIn('data-chat-mode="explore"', index)
                self.assertIn('data-chat-mode="mission"', index)
                self.assertIn('id="explore-context"', index)
                self.assertIn('id="explore-agent-mode"', index)
                self.assertIn('data-explore-agent-mode="read"', index)
                self.assertIn('data-explore-agent-mode="propose"', index)
                self.assertIn('data-explore-agent-mode="implement"', index)
                self.assertIn('id="explore-pins"', index)
                self.assertIn('id="chat-microphone"', index)
                self.assertIn('id="chat-speech"', index)
                self.assertIn('id="shortcut-dialog"', index)
                self.assertIn('id="command-palette-dialog"', index)
                self.assertIn('id="diagram-dialog"', index)
                self.assertIn('id="projection-dialog"', index)
                self.assertIn('id="projection-depth"', index)
                self.assertIn('id="projection-open"', index)
                self.assertIn('id="project-node"', index)
                self.assertIn('data-command="selection.project"', index)
                self.assertIn('id="graph-projection-bar"', index)
                self.assertIn('id="graph-projection-back"', index)
                self.assertIn('id="graph-projection-fit"', index)
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
                self.assertIn('src="/flow-navigation.js"', index)
                self.assertIn('src="/graph-views.js"', index)
                self.assertIn('src="/panel-layout.js"', index)
                self.assertIn('src="/explore.js"', index)
                self.assertIn('src="/rich-render.js"', index)
                self.assertIn('src="/diagrams.js"', index)
                self.assertIn('src="/graph-projection.js"', index)
                self.assertIn('src="/commands.js"', index)
                self.assertLess(index.index('src="/rich-render.js"'), index.index('src="/mission.js"'))
                self.assertLess(index.index('src="/flow-navigation.js"'), index.index('src="/graph-views.js"'))
                self.assertLess(index.index('src="/graph-views.js"'), index.index('src="/app.js"'))
                self.assertLess(index.index('src="/graph-render.js"'), index.index('src="/panel-layout.js"'))
                self.assertLess(index.index('src="/panel-layout.js"'), index.index('src="/explore.js"'))
                self.assertLess(index.index('src="/explore.js"'), index.index('src="/diagrams.js"'))
                self.assertLess(index.index('src="/diagrams.js"'), index.index('src="/graph-projection.js"'))
                self.assertLess(index.index('src="/graph-projection.js"'), index.index('src="/commands.js"'))
                self.assertLess(index.index('id="project-open"'), index.index('class="mission-presence"'))
                navigate_group = index.index('id="graph-tools-navigate"')
                inspect_group = index.index('id="graph-tools-inspect"')
                design_group = index.index('id="design-tools-title"')
                draft_group = index.index('id="graph-tools-draft"')
                more_menu = index.index('id="graph-more"')
                self.assertLess(index.index('id="design-mode-toggle"'), more_menu)
                self.assertLess(index.index('id="canvas-focus"'), more_menu)
                self.assertLess(more_menu, index.index('id="hide-node"'))
                self.assertLess(index.index('id="reset-view"'), index.index('class="design-legend"'))
                self.assertLess(index.index('class="design-legend"'), navigate_group)
                self.assertLess(navigate_group, inspect_group)
                self.assertLess(inspect_group, design_group)
                self.assertLess(design_group, index.index('id="add-node"'))
                self.assertLess(index.index('id="add-node"'), index.index('id="add-relation"'))
                self.assertLess(index.index('id="add-relation"'), index.index('id="edit-node"'))
                self.assertLess(index.index('id="edit-node"'), index.index('id="delete-node"'))
                self.assertLess(index.index('id="delete-node"'), draft_group)
                self.assertLess(draft_group, index.index('id="sync-design"'))
                self.assertIn("Discard draft", index)
                self.assertNotIn('class="project-panel" aria-labelledby="design-tools-title"', index)
                self.assertEqual(index.count('role="separator"'), 3)
                self.assertNotIn(">Topology<", index)
                self.assertNotIn(">Hybrid<", index)
                self.assertEqual(index.count("<!doctype html>"), 1)

                with urlopen(f"{base_url}/mission.js") as response:
                    mission_script = response.read().decode("utf-8")
                with urlopen(f"{base_url}/explore.js") as response:
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    explore_script = response.read().decode("utf-8")
                with urlopen(f"{base_url}/app.js") as response:
                    app_script = response.read().decode("utf-8")
                with urlopen(f"{base_url}/architecture-scenarios.js") as response:
                    scenario_script = response.read().decode("utf-8")
                with urlopen(f"{base_url}/flow-navigation.js") as response:
                    flow_navigation_script = response.read().decode("utf-8")
                with urlopen(f"{base_url}/graph-views.js") as response:
                    graph_views_script = response.read().decode("utf-8")
                with urlopen(f"{base_url}/panel-layout.js") as response:
                    panel_layout_script = response.read().decode("utf-8")
                with urlopen(f"{base_url}/rich-render.js") as response:
                    rich_render_script = response.read().decode("utf-8")
                with urlopen(f"{base_url}/commands.js") as response:
                    commands_script = response.read().decode("utf-8")
                with urlopen(f"{base_url}/diagrams.js") as response:
                    diagrams_script = response.read().decode("utf-8")
                with urlopen(f"{base_url}/graph-projection.js") as response:
                    projection_script = response.read().decode("utf-8")
                with urlopen(f"{base_url}/graph-render.js") as response:
                    graph_script = response.read().decode("utf-8")
                with urlopen(f"{base_url}/styles.css") as response:
                    styles = response.read().decode("utf-8")
                self.assertIn("function renderJsonPreview", mission_script)
                self.assertIn("function renderTaskWorkplan", mission_script)
                self.assertIn("function contractPreview", mission_script)
                self.assertIn("owner ${owner}", mission_script)
                self.assertIn("function appendDocumentGroup", mission_script)
                self.assertIn("agent_progress", mission_script)
                self.assertIn("function activityMetrics", mission_script)
                self.assertIn("function selectLocalProject", mission_script)
                self.assertIn("function openProjectDialog", mission_script)
                self.assertIn("projectDialog.showModal()", mission_script)
                self.assertIn('jsonOptions("POST", { path: projectPath })', mission_script)
                self.assertIn("function currentExploreContext", explore_script)
                self.assertIn("function renderPinnedNodes", explore_script)
                self.assertIn("function draftSnapshot", scenario_script)
                self.assertIn('fetchJson("/api/scenarios"', scenario_script)
                self.assertIn("renderComparison(result, comparison)", scenario_script)
                self.assertIn("HeroArchitectureScenarios?.install", app_script)
                self.assertIn("function updateExploreBusyState", explore_script)
                self.assertIn("applyAgentGraphProposals(session.actions", explore_script)
                self.assertIn("async function pollMcpProposals", explore_script)
                self.assertIn("function proposalNeedsObservedGraphRefresh", explore_script)
                self.assertIn("await loadExperiment({ restoreLocalDesign: true })", explore_script)
                self.assertIn('fetch("/api/mcp/proposals"', explore_script)
                self.assertIn('fetch("/api/mcp/proposals/ack"', explore_script)
                self.assertIn("setInterval(pollMcpProposals, 1000)", explore_script)
                self.assertIn('classList.toggle("model-pending", busy)', explore_script)
                self.assertIn("pinnedNodeIds", explore_script)
                self.assertIn("assistantMode: exploreState.agentMode", explore_script)
                self.assertIn("proposalNodes", explore_script)
                self.assertIn("function revealAgentProposal", app_script)
                self.assertIn("expandTreePath(nodeId)", app_script)
                self.assertIn("!isDescendantOf(nodeId, state.scope)", app_script)
                self.assertIn('state.view === "flow" && state.flowJourney.length', app_script)
                self.assertIn("revealAgentProposal(state.selected)", app_script)
                self.assertIn("proposalRendered ? lastNodeId : previousSelection", app_script)
                self.assertIn("state.graph.nodes.filter((candidate) => !removedNodeIds.has(candidate.id))", app_script)
                self.assertIn("!removedNodeIds.has(edge.source) && !removedNodeIds.has(edge.target)", app_script)
                self.assertIn("nonProposedDescendants", app_script)
                self.assertIn("render();", app_script[app_script.index("function applyAgentGraphProposals"):app_script.index("globalThis.applyAgentGraphProposals")])
                self.assertIn("BrowserSpeechRecognition", explore_script)
                self.assertIn("SpeechSynthesisUtterance", explore_script)
                self.assertIn("RichContentRenderer.render", explore_script)
                self.assertIn("function submitExplorePrompt", explore_script)
                self.assertIn("submitExplorePrompt(text, context = currentExploreContext())", explore_script)
                self.assertIn('if (message.role === "user") body.textContent = message.content', explore_script)
                self.assertIn("heading.append(globalThis.createChatCopyButton(message.content))", explore_script)
                self.assertIn('if (visualRole === "agent") heading.append(globalThis.createChatCopyButton(message.content))', mission_script)
                self.assertIn("async function copyTextToClipboard", app_script)
                self.assertIn('button.setAttribute("aria-label", "Copy agent response")', app_script)
                self.assertIn('securityLevel: "strict"', rich_render_script)
                self.assertIn("DOMPurify.sanitize(parsed", rich_render_script)
                self.assertIn("USE_PROFILES: { svg: true, svgFilters: true }", rich_render_script)
                self.assertIn("function emphasizeDirectionMarkers", rich_render_script)
                self.assertIn("function tryMermaidEnhancement", rich_render_script)
                self.assertIn('tryMermaidEnhancement("interaction"', rich_render_script)
                self.assertIn("showMermaidError(diagram, error, definition)", rich_render_script)
                self.assertIn('summary.textContent = "Show Mermaid source"', rich_render_script)
                self.assertIn("Diagram could not be rendered", rich_render_script)
                self.assertIn("RichContentRenderer.render(preview", mission_script)
                self.assertIn('id: "selection.explain"', commands_script)
                self.assertIn('id: "selection.diagram"', commands_script)
                self.assertIn('id: "selection.project"', commands_script)
                self.assertIn('g: "selection.project"', commands_script)
                self.assertIn("function focusRenderedGraphNode", app_script)
                self.assertIn("focusRenderedGraphNode(completedDrag.nodeId)", app_script)
                self.assertIn('focusReturnView: "flow"', app_script)
                self.assertIn("const selectedAtEntry = state.selected;", app_script)
                self.assertIn('if (view === "focus" && savedView?.selected !== selectedAtEntry)', app_script)
                self.assertIn('setGraphView(state.focusReturnView || "flow")', app_script)
                self.assertIn('const resetFromFocus = state.view === "focus";', app_script)
                self.assertIn('commandId === "node.toggle-expansion"', commands_script)
                self.assertIn("focusRenderedGraphNode()", commands_script)
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
                self.assertIn("function recommendedProjection", projection_script)
                self.assertIn('type: "neighborhood", view: "flow", label: "Module neighborhood"', projection_script)
                self.assertIn("function activateProjection", projection_script)
                self.assertIn("function validateProjectionChoice", projection_script)
                self.assertIn("projectionForm.addEventListener", projection_script)
                self.assertIn("function setProjectionDepth", projection_script)
                self.assertIn("function expandProjection", projection_script)
                self.assertIn("function backProjection", projection_script)
                self.assertIn("function restoreProjection", projection_script)
                self.assertIn('setCanvasFocus("projection", true)', projection_script)
                self.assertIn('setCanvasFocus("projection", false)', projection_script)
                self.assertIn('querySelector("#graph-projection-fit").addEventListener("click", fitGraphToView)', projection_script)
                activate_projection_script = projection_script[projection_script.index("function activateProjection"):projection_script.index("function containmentExpansion")]
                restore_projection_script = projection_script[projection_script.index("function restoreProjection"):projection_script.index("function backProjection")]
                back_projection_script = projection_script[projection_script.index("function backProjection"):projection_script.index("function projectSelection")]
                self.assertIn("focusRenderedGraphNode()", activate_projection_script)
                self.assertIn("focusRenderedGraphNode()", restore_projection_script)
                self.assertIn("focusRenderedGraphNode()", back_projection_script)
                self.assertIn("function mergeGraphs", projection_script)
                self.assertIn("G, E, or double-click", projection_script)
                self.assertNotIn("function activateProjection", diagrams_script)
                self.assertIn("promptVersion: 1", diagrams_script)
                self.assertEqual(diagrams_script.count("deterministic: true"), 6)
                self.assertEqual(diagrams_script.count("deterministic: false"), 1)
                self.assertNotIn('addEventListener("click", toggleCallTrace)', app_script)
                self.assertIn('retry: { endpoint: "retry-review"', mission_script)
                self.assertIn("function rebuildGraphIndexes", app_script)
                self.assertIn("function applyAgentGraphProposals", app_script)
                self.assertIn("renderProposalContract", app_script)
                self.assertIn("target_path", app_script)
                self.assertIn("qualified_name", app_script)
                self.assertIn("proposal-contract.js", index)
                self.assertIn("replayed", app_script[app_script.index("function applyAgentGraphProposals"):app_script.index("globalThis.applyAgentGraphProposals")])
                self.assertIn("function reconcileStoredDesign", app_script)
                self.assertIn("return reconcileStoredDesign(baseGraph, stored.graph)", app_script)
                self.assertIn('designProvenance: "AGENT"', app_script)
                self.assertIn("state.childrenByParent.get(scopeId)", app_script)
                self.assertIn("function structureGraph", app_script)
                self.assertIn("function focusGraph", app_script)
                self.assertIn("function navigateGraphBack", app_script)
                self.assertIn("function callTraceGraph", app_script)
                self.assertIn("if (state.callTrace) return callTraceGraph();", app_script)
                self.assertIn("if (state.graphProjection) return state.graphProjection.graph;", app_script)
                self.assertIn("HeroDiagrams?.expandProjection(completedDrag.nodeId)", app_script)
                self.assertIn('projectionActive ? "Expand node" : canFollow && !canExpand ? "Follow" : "Expand"', app_script)
                self.assertIn("trace.returnView = {", app_script)
                self.assertIn("clearCallTrace({ restoreViewport: true })", app_script)
                self.assertIn("Previous view restored", app_script)
                self.assertIn('state.callTrace ? "Restore view" : "Trace calls"', app_script)
                self.assertIn("graphViews.flowGraph(graphViewContext(), expandedNodes)", app_script)
                self.assertIn("function flowJourneyGraph", app_script)
                self.assertIn("context.flowJourney.map((step) => step.nodeId)", graph_views_script)
                self.assertIn("flowJourney: state.flowJourney", app_script)
                self.assertIn("state.flowEntryCandidate", app_script)
                self.assertIn("flowNavigation.appendStep", app_script)
                self.assertIn("flowNavigation.truncateJourney", app_script)
                self.assertIn("flowNavigation.migrateLegacyJourney", app_script)
                self.assertNotIn("state.flowOrigin", app_script)
                self.assertNotIn("state.flowTrail", app_script)
                self.assertIn("function appendStep", flow_navigation_script)
                self.assertIn("function pruneJourney", flow_navigation_script)
                self.assertIn("function focusGraph", graph_views_script)
                self.assertIn("function outgoingCallTrace", graph_views_script)
                self.assertIn("return flowJourneyGraph()", app_script)
                self.assertIn("updateGraphSelectionStyles", graph_script)
                self.assertIn("state.graphProjection?.savedLayout", graph_script)
                self.assertIn("!state.graphProjection", graph_script)
                self.assertIn("function setGraphView", app_script)
                self.assertIn("function setGraphDesignMode", app_script)
                self.assertIn('querySelector("#design-mode-toggle").addEventListener', app_script)
                self.assertIn("function captureGraphViewState", app_script)
                self.assertIn("function graphProjectionKey", app_script)
                self.assertIn("state.viewStates[state.view]", app_script)
                self.assertIn('if (state.view === "focus") return;', app_script)
                self.assertIn("function setGraphZoom", app_script)
                self.assertIn("const fittedScale = Math.min(availableWidth / state.graphWidth, availableHeight / state.graphHeight)", app_script)
                stop_drag_script = app_script[app_script.index("function stopDrag"):app_script.index("function setSelection")]
                expand_index = stop_drag_script.index('else if (state.view === "flow" || canEnterScope(completedDrag.nodeId)) expandSelectedNode();')
                self.assertGreater(stop_drag_script.index("fitGraphToView();"), expand_index)
                self.assertIn("GRAPH_FIT_PADDING", app_script)
                self.assertIn("function startGraphPan", app_script)
                self.assertIn("function toggleGraphLayoutLock", app_script)
                self.assertIn("if (state.layoutLocked && state.layoutSnapshot) return state.layoutSnapshot.graph", app_script)
                self.assertIn("function updateCodeSearch", app_script)
                self.assertIn("function initializeTypography", panel_layout_script)
                self.assertIn("hero-graph-lab-typography-v1", panel_layout_script)
                self.assertIn("hero-graph-lab-layout-v2", panel_layout_script)
                self.assertIn('collapsed: ["code"]', panel_layout_script)
                self.assertIn("function setCanvasFocus", panel_layout_script)
                self.assertIn('setCanvasFocus("manual"', panel_layout_script)
                self.assertIn('addEventListener("mission-document-opened"', app_script)
                self.assertIn("function normalizeLayout", panel_layout_script)
                self.assertIn('HeroPanelLayout.expand("inspector")', explore_script)
                self.assertIn("state.treeExpanded = new Set(state.graph.root ? [state.graph.root] : []);", app_script)
                self.assertIn("function selectionDimmingActive", graph_script)
                self.assertIn('!state.graphProjection && state.view !== "structure"', graph_script)
                self.assertIn("activeAnchor: state.selected", projection_script)
                self.assertIn("selected: projection.activeAnchor", projection_script)
                self.assertIn("function focusLayout", graph_script)
                self.assertIn("function structureLayout", graph_script)
                self.assertIn("function graphNodeMetrics", graph_script)
                self.assertIn("function nodeBoundaryPoint", graph_script)
                self.assertIn('"marker-end": edgeMarker(edge.status)', graph_script)
                self.assertIn("function relationLabelOffsets", graph_script)
                self.assertIn("const scale = graphTextScale()", graph_script)
                self.assertIn('visualRole = role === "human" || role === "user"', mission_script)
                self.assertIn(".chat-message.human { align-self: flex-end", styles)
                self.assertIn(".chat-message.agent { align-self: flex-start", styles)
                self.assertIn(".chat-copy-button { min-height: 24px", styles)
                self.assertIn("grid-template-rows: auto auto auto minmax(0, 1fr) auto", styles)
                self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", styles)
                self.assertIn(".chat-form > .chat-actions { display: flex", styles)
                self.assertIn(".chat-form .submit-button { min-width: 68px; margin-left: auto", styles)
                self.assertIn(".chat-form:focus-within { border-color: var(--inspector-accent)", styles)
                self.assertIn("body.model-pending, body.model-pending * { cursor: progress !important; }", styles)
                self.assertIn(".scope-crumb.trail-crumb", styles)
                self.assertIn(".canvas-shell { position: relative; min-width: 0; overflow: hidden; display: grid; grid-template-rows: auto auto auto minmax(0, 1fr)", styles)
                self.assertIn(".graph-control-strip { position: relative", styles)
                self.assertIn(".graph-tool-actions { min-width: 0; display: flex; flex-wrap: wrap", styles)
                self.assertIn(".graph-viewport { position: relative; grid-row: 4", styles)
                self.assertIn(".graph-viewport { position: relative; grid-row: 4; grid-column: 1", styles)
                self.assertNotIn(".graph-viewport { position: absolute; inset: 192px", styles)
                self.assertNotIn(".graph-control-strip { position: absolute", styles)
                self.assertIn("body.projection-focus-mode .graph-control-strip", styles)
                self.assertIn("body.canvas-focus-mode .workspace", styles)
                self.assertIn("grid-template-columns: minmax(0, 1fr) !important", styles)
                self.assertIn("grid-template-rows: minmax(0, 1fr) !important", styles)
                self.assertIn("body.explorer-collapsed .explorer-heading .panel-heading-actions > :not(.panel-collapse)", styles)
                self.assertNotIn("body.explorer-collapsed .panel-heading-actions {", styles)
                self.assertIn("body.graph-design-mode .design-tools", styles)
                self.assertIn("@container (max-width: 720px)", styles)
                self.assertIn("@media (max-width: 980px)", styles)
                self.assertNotIn("@media (max-width: 900px)", styles)
                self.assertIn(".graph-more-menu-content { position: absolute", styles)
                self.assertIn(".workplan-list", styles)
                self.assertIn(".document-group-list", styles)
                self.assertIn(".activity-agent_progress", styles)
                self.assertIn("--accent: #0f766e", styles)
                self.assertIn('--sans: Inter, "Segoe UI", system-ui', styles)
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

    def test_mcp_tool_gateway_and_proposal_delivery_contract(self) -> None:
        with TemporaryDirectory() as directory:
            state = LabState(FIXTURE, Path(directory) / "observations.json")
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                with urlopen(f"{base_url}/api/mcp/tools") as response:
                    tools = json.load(response)
                self.assertIn("GraphSearch", {tool["name"] for tool in tools["tools"]})

                parent = next(node for node in state.graph()["nodes"] if node["kind"] == "module")
                proposal_request = Request(
                    f"{base_url}/api/mcp/tools/ProposeNode",
                    data=json.dumps(
                        {
                            "arguments": {
                                "label": "TelegramGateway",
                                "kind": "class",
                                "parent_id": parent["id"],
                            }
                        }
                    ).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(proposal_request) as response:
                    proposed = json.load(response)
                self.assertEqual(proposed["actions"][0]["op"], "add_node")

                with urlopen(f"{base_url}/api/mcp/proposals") as response:
                    pending = json.load(response)
                self.assertEqual(pending["items"][0]["revision"], 1)

                ack_request = Request(
                    f"{base_url}/api/mcp/proposals/ack",
                    data=json.dumps({"revisions": [1]}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(ack_request) as response:
                    acknowledged = json.load(response)
                self.assertEqual(acknowledged["items"], [])

                invalid_request = Request(
                    f"{base_url}/api/mcp/tools/ProposeNode",
                    data=json.dumps({"arguments": []}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(HTTPError) as raised:
                    urlopen(invalid_request)
                self.assertEqual(raised.exception.code, 400)
                self.assertIn("arguments must be a JSON object", json.load(raised.exception)["error"])
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
                invalid_paths = (
                    ("", "must not be empty"),
                    ("relative-project", "must be absolute"),
                    (str(Path(directory) / "missing"), "folder not found"),
                )
                for invalid_path, detail in invalid_paths:
                    invalid_request = Request(
                        f"{base_url}/api/project/select",
                        data=json.dumps({"path": invalid_path}).encode(),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with self.assertRaises(HTTPError) as raised:
                        urlopen(invalid_request)
                    self.assertEqual(raised.exception.code, 400)
                    self.assertIn(detail, json.load(raised.exception)["detail"])
                    self.assertFalse(state.project_selected)
                    self.assertTrue(state.fixture.samefile(FIXTURE))
                select_request = Request(
                    f"{base_url}/api/project/select",
                    data=json.dumps({"path": str(selected_project)}).encode(),
                    headers={"Content-Type": "application/json"},
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
