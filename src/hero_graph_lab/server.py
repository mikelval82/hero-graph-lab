from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
from dataclasses import replace
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from hero_graph_lab.architecture import ArchitectureScenarioService, ContractImpactAnalyzer
from hero_graph_lab.contracts import (
    ContractRepository,
    ContractStatus,
    ExecutionEvidence,
    ExecutionRequest,
    IntentContract,
    ReconciliationResult,
    SourceSnapshot,
    VerificationPolicy,
    validate_contract,
)
from hero_graph_lab.contracts.serialization import dumps as contract_dumps, loads as contract_loads
from hero_graph_lab.extractor import extract_project_graph, project_source_files
from hero_graph_lab.contract_gateway import ContractGateway, HarnessContractGateway
from hero_graph_lab.explore import ExploreAssistantService, create_model_client
from hero_graph_lab.explore.gateway import MCP_INSTRUCTIONS, GraphToolGateway
from hero_graph_lab.explore.models import ModelClient
from hero_graph_lab.harness_host import HarnessHostError, HarnessWorkerHost
from hero_graph_lab.execution import ExecutionRegistry


PROJECT_ROOT = Path(__file__).parents[2]
STATIC_ROOT = Path(__file__).parent / "static"
DEFAULT_FIXTURE = PROJECT_ROOT / "fixtures" / "order_app"
DEFAULT_STATE = PROJECT_ROOT / "state" / "observations.json"
DEFAULT_HARNESS_ROOT = PROJECT_ROOT.parent / "HARNESS"
ALLOWED_VIEWS = {"flow"}
MAX_REQUEST_BYTES = 2 * 1024 * 1024


def detect_harness_root() -> Path:
    candidates = [
        PROJECT_ROOT.parent / "hero-harness",
        PROJECT_ROOT.parent / "HARNESS",
        PROJECT_ROOT.parent / "mission-orchestrator",
        Path.cwd() / "hero-harness",
        Path.cwd() / "HARNESS",
    ]
    for candidate in candidates:
        if candidate.exists() and (candidate / "src" / "mission_orchestrator").is_dir():
            return candidate.resolve()
    return (PROJECT_ROOT.parent / "hero-harness").resolve()


def detect_harness_python(harness_root: Path) -> Path | None:
    candidate_paths = [
        harness_root / ".venv" / "bin" / "python",
        harness_root / ".venv" / "bin" / "python3",
        harness_root / ".venv" / "Scripts" / "python.exe",
        harness_root / ".venv" / "Scripts" / "python",
    ]
    for candidate in candidate_paths:
        if candidate.is_file():
            return candidate.absolute()
    return None


class LabState:
    def __init__(
        self,
        fixture: Path,
        observations_path: Path,
        harness_host: HarnessWorkerHost | None = None,
        project_selected: bool = False,
        explore_client: ModelClient | None = None,
    ) -> None:
        self.fixture = fixture
        self.observations_path = observations_path
        self.scenarios = ArchitectureScenarioService(
            observations_path.with_name("architecture-scenarios.json"),
            lambda: self.fixture,
        )
        self.contract_impact = ContractImpactAnalyzer()
        self.contract_repository = ContractRepository(self.fixture)
        self.execution_registry = ExecutionRegistry(self.fixture)
        self.execution_requests: dict[str, ExecutionRequest] = {}
        self.execution_evidence: dict[str, list[ExecutionEvidence]] = {}
        self.harness_host = harness_host
        self.project_selected = project_selected
        self._lock = threading.RLock()
        self._graph_cache: dict[str, Any] | None = None
        self._graph_fixture: Path | None = None
        self._graph_fingerprint: tuple[tuple[str, int, int], ...] | None = None
        self.graph_tools = GraphToolGateway(lambda: self.fixture, self.graph)
        self.contract_tools = (
            HarnessContractGateway(harness_host)
            if harness_host is not None
            else ContractGateway(self)
        )
        self.chat_contract_tools = self.contract_tools
        self.explore = ExploreAssistantService(
            explore_client or create_model_client("fake"),
            lambda: self.fixture,
            self.graph,
            tools=self.graph_tools.registry,
            contract_tools=self.chat_contract_tools,
        )

    def graph(self) -> dict[str, Any]:
        with self._lock:
            fixture = self.fixture.resolve()
            fingerprint = self._source_fingerprint(fixture)
            if (
                self._graph_cache is None
                or self._graph_fixture != fixture
                or self._graph_fingerprint != fingerprint
            ):
                self._graph_cache = extract_project_graph(fixture)
                self._graph_fixture = fixture
                self._graph_fingerprint = fingerprint
            return self._graph_cache

    def set_fixture(self, fixture: Path) -> None:
        with self._lock:
            self.fixture = fixture.resolve()
            self._graph_cache = None
            self._graph_fixture = None
            self._graph_fingerprint = None
            self.graph_tools.reset()
            self.contract_repository = ContractRepository(self.fixture)
            self.execution_registry = ExecutionRegistry(self.fixture)

    def capabilities(self) -> dict[str, object]:
        return {
            "executor_required": False,
            "legacy_harness": self.harness_host is not None,
            "contracts": True,
            "handoffs": True,
            "executors": self.execution_registry.capabilities(),
        }

    def list_contracts(self) -> list[dict[str, object]]:
        return [json.loads(contract_dumps(item)) for item in self.contract_repository.list()]

    def create_contract(self, payload: dict[str, Any]) -> dict[str, object]:
        contract = IntentContract(
            id=str(payload.get("id") or uuid4()),
            title=str(payload.get("title", "")),
            objective=str(payload.get("objective", "")),
            requirements=list(payload.get("requirements", [])),
            acceptance_criteria=list(payload.get("acceptance_criteria", [])),
            metadata=payload.get("metadata", {}) if isinstance(payload.get("metadata", {}), dict) else {},
        )
        contract = validate_contract(contract)
        path = self.contract_repository.save(contract)
        return json.loads(contract_dumps(contract)) | {"path": str(path)}

    def get_contract(self, contract_id: str) -> dict[str, object]:
        return json.loads(contract_dumps(self.contract_repository.get(contract_id)))

    def validate_contract(self, contract_id: str) -> dict[str, object]:
        contract = validate_contract(self.contract_repository.get(contract_id))
        self.contract_repository.save(contract)
        return {"valid": True, "contract": json.loads(contract_dumps(contract))}

    def export_handoff(self, contract_id: str, payload: dict[str, Any]) -> dict[str, object]:
        contract = validate_contract(self.contract_repository.get(contract_id))
        policy = VerificationPolicy(
            commands=[str(item) for item in payload.get("commands", [])],
            required_paths=[str(item) for item in payload.get("required_paths", [])],
            required_relationships=list(payload.get("required_relationships", [])),
        )
        snapshot = self._source_snapshot()
        handed_off = replace(contract, status=ContractStatus.HANDED_OFF)
        execution_id = str(payload.get("execution_id") or uuid4())
        request = ExecutionRequest(handed_off, snapshot, policy, str(payload.get("instructions", "")), execution_id)
        executor = self.execution_registry.get(str(payload.get("executor", "manual")))
        receipt = executor.handoff(request)
        self.contract_repository.save(handed_off)
        self.execution_requests[receipt.execution_id] = request
        return json.loads(contract_dumps(receipt))

    def execution_status(self, execution_id: str) -> dict[str, object]:
        request = self._request_for_execution(execution_id)
        if request is None:
            raise KeyError(execution_id)
        return self.execution_registry.get("manual").status(execution_id) | {"evidence": [json.loads(contract_dumps(item)) for item in self.execution_evidence.get(execution_id, [])]}

    def record_evidence(self, execution_id: str, payload: dict[str, Any]) -> dict[str, object]:
        request = self._request_for_execution(execution_id)
        if request is None:
            raise KeyError(execution_id)
        evidence = ExecutionEvidence(
            execution_id,
            str(payload.get("revision", "")),
            [str(item) for item in payload.get("changed_files", [])],
            list(payload.get("commands", [])),
            str(payload.get("notes", "")),
            payload.get("artifacts", {}) if isinstance(payload.get("artifacts", {}), dict) else {},
        )
        self.execution_evidence.setdefault(execution_id, []).append(evidence)
        self.contract_repository.save(replace(request.contract, status=ContractStatus.VERIFYING))
        target = self.fixture / ".graph-lab" / "evidence" / f"{execution_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contract_dumps(self.execution_evidence[execution_id]), encoding="utf-8")
        return json.loads(contract_dumps(evidence))

    def reconcile(self, contract_id: str, execution_id: str) -> dict[str, object]:
        contract = self.contract_repository.get(contract_id)
        request = self._request_for_execution(execution_id)
        if request is None:
            raise KeyError(execution_id)
        graph = self.graph()
        actual_paths = {str(node.get("source")) for node in graph.get("nodes", []) if node.get("source")}
        missing = sorted(set(request.verification_policy.required_paths) - actual_paths)
        relationships = {(item.get("source"), item.get("target"), item.get("kind")) for item in graph.get("edges", [])}
        divergent = [str(item) for item in request.verification_policy.required_relationships if (item.get("source"), item.get("target"), item.get("kind")) not in relationships]
        status = ContractStatus.MATERIALIZED if not missing and not divergent else ContractStatus.DIVERGENT
        result = ReconciliationResult(contract.id, status, sorted(actual_paths & set(request.verification_policy.required_paths)), missing, divergent)
        self.contract_repository.save(replace(contract, status=status))
        return json.loads(contract_dumps(result))

    def _source_snapshot(self) -> SourceSnapshot:
        files: dict[str, dict[str, object]] = {}
        for path in project_source_files(self.fixture):
            relative = path.name if self.fixture.is_file() else path.relative_to(self.fixture).as_posix()
            content = path.read_bytes()
            files[relative] = {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}
        return SourceSnapshot(self.graph().get("root", ""), self.graph(), files, datetime.now(UTC).isoformat())

    def _request_for_execution(self, execution_id: str) -> ExecutionRequest | None:
        request = self.execution_requests.get(execution_id)
        if request is not None:
            return request
        handoff = self.fixture / ".graph-lab" / "handoffs" / execution_id
        try:
            contract_payload = contract_loads((handoff / "contract.json").read_text(encoding="utf-8"))
            snapshot_payload = contract_loads((handoff / "source-snapshot.json").read_text(encoding="utf-8"))
            policy_payload = contract_loads((handoff / "verification-policy.json").read_text(encoding="utf-8"))
            contract_values = dict(contract_payload)
            contract_values["status"] = ContractStatus(contract_payload.get("status", "DRAFT"))
            contract = IntentContract(**contract_values)
            request = ExecutionRequest(
                contract,
                SourceSnapshot(**snapshot_payload),
                VerificationPolicy(**policy_payload),
                execution_id=execution_id,
            )
        except (FileNotFoundError, OSError, TypeError, ValueError, json.JSONDecodeError):
            return None
        self.execution_requests[execution_id] = request
        return request

    @staticmethod
    def _source_fingerprint(fixture: Path) -> tuple[tuple[str, int, int], ...]:
        root = fixture.parent if fixture.is_file() else fixture
        fingerprint = []
        for file in project_source_files(fixture):
            metadata = file.stat()
            fingerprint.append(
                (
                    file.relative_to(root).as_posix(),
                    metadata.st_mtime_ns,
                    metadata.st_size,
                )
            )
        return tuple(fingerprint)

    def source(self) -> dict[str, Any]:
        if self.fixture.is_file():
            files = [self.fixture]
            root = self.fixture.parent
        else:
            files = project_source_files(self.fixture)
            root = self.fixture
        sources = {}
        for file in files:
            content = file.read_text(encoding="utf-8")
            source = file.name if self.fixture.is_file() else file.relative_to(root).as_posix()
            sources[source] = {
                "content": content,
                "line_count": len(content.splitlines()),
            }
        payload: dict[str, Any] = {"source": self.fixture.name, "sources": sources}
        if self.fixture.is_file():
            payload.update(sources[self.fixture.name])
        return payload

    def observations(self) -> dict[str, list[dict[str, Any]]]:
        with self._lock:
            return self._read_observations()

    def add_observation(self, payload: dict[str, Any]) -> dict[str, Any]:
        view = payload.get("view")
        notes = payload.get("notes")
        decision = payload.get("decision", "undecided")
        friction = payload.get("friction")
        if view not in ALLOWED_VIEWS:
            raise ValueError("view must be flow")
        if not isinstance(notes, str) or not notes.strip():
            raise ValueError("notes must not be empty")
        if decision not in {"keep", "change", "discard", "undecided"}:
            raise ValueError("invalid decision")
        if not isinstance(friction, int) or not 1 <= friction <= 5:
            raise ValueError("friction must be an integer from 1 to 5")

        observation = {
            "id": str(uuid4()),
            "created_at": datetime.now(UTC).isoformat(),
            "view": view,
            "task": str(payload.get("task", "free exploration")),
            "friction": friction,
            "decision": decision,
            "notes": notes.strip(),
        }
        with self._lock:
            document = self._read_observations()
            document["observations"].append(observation)
            self.observations_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.observations_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            temporary.replace(self.observations_path)
        return observation

    def select_project(self, project_path: Path) -> dict[str, object]:
        if not project_path.is_absolute():
            raise ValueError("project path must be absolute")
        project = project_path.resolve()
        if not project.is_dir():
            raise ValueError(f"project folder not found: {project}")
        self.harness_host.configure_project(project)
        with self._lock:
            self.fixture = project
            self.project_selected = True
            self._graph_cache = None
            self._graph_fixture = None
            self._graph_fingerprint = None
            self.graph_tools.reset()
        return self.harness_status()

    def harness_status(self) -> dict[str, object]:
        status = (
            self.harness_host.status()
            if self.harness_host is not None
            else {"configured": False, "running": False}
        )
        return status | {"project_selected": self.project_selected}

    def _read_observations(self) -> dict[str, list[dict[str, Any]]]:
        if not self.observations_path.exists():
            return {"observations": []}
        payload = json.loads(self.observations_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("observations"), list):
            raise ValueError("observation state is malformed")
        return payload

def initial_project(fixture: Path, mission_project: Path | None) -> Path:
    return (mission_project or fixture).resolve()


def make_handler(state: LabState) -> type[BaseHTTPRequestHandler]:
    class LabRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/api/graph":
                self._send_json(state.graph())
                return
            if path == "/api/capabilities":
                self._send_json(state.capabilities())
                return
            if path == "/api/contracts":
                self._send_json({"contracts": state.list_contracts()})
                return
            contract_id = self._contract_id(path)
            if contract_id:
                if contract_id.startswith("execution:"):
                    try:
                        self._send_json(state.execution_status(contract_id.removeprefix("execution:")))
                    except KeyError:
                        self._send_json({"error": "execution_not_found"}, HTTPStatus.NOT_FOUND)
                    return
                try:
                    self._send_json(state.get_contract(contract_id))
                except (KeyError, FileNotFoundError):
                    self._send_json({"error": "contract_not_found"}, HTTPStatus.NOT_FOUND)
                return
            if path == "/api/source":
                self._send_json(state.source())
                return
            if path == "/api/observations":
                self._send_json(state.observations())
                return
            if path == "/api/scenarios":
                self._send_json({"scenarios": state.scenarios.list()})
                return
            scenario_id = self._scenario_id(path)
            if scenario_id:
                try:
                    self._send_json(state.scenarios.get(scenario_id))
                except KeyError as error:
                    self._send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
                except ValueError as error:
                    self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            if path == "/api/harness/status":
                self._send_json(state.harness_status())
                return
            if path == "/api/explore/status":
                self._send_json(state.explore.status())
                return
            if path == "/api/mcp/tools":
                self._send_json(
                    {
                        "instructions": MCP_INSTRUCTIONS,
                        "tools": [
                            *state.graph_tools.tool_specs(),
                            *state.contract_tools.tool_specs(),
                        ],
                    }
                )
                return
            if path == "/api/mcp/proposals":
                self._send_json(state.graph_tools.pending_proposals())
                return
            session_id = self._explore_session_id(path)
            if session_id:
                try:
                    self._send_json(state.explore.session(session_id))
                except KeyError as error:
                    self._send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
                return
            if path.startswith("/api/harness/v1/"):
                self._proxy_harness("GET", parsed)
                return
            self._serve_static(path)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/project/select":
                self._select_project()
                return
            if parsed.path == "/api/contracts":
                try:
                    self._send_json(state.create_contract(self._read_json()), HTTPStatus.CREATED)
                except (ValueError, json.JSONDecodeError) as error:
                    self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            contract_action = self._contract_action(parsed.path)
            if contract_action:
                contract_id, action = contract_action
                try:
                    payload = self._read_json()
                    if action == "validate":
                        result = state.validate_contract(contract_id)
                    elif action == "handoff":
                        result = state.export_handoff(contract_id, payload)
                    elif action == "reconcile":
                        result = state.reconcile(contract_id, str(payload.get("execution_id", contract_id)))
                    else:
                        raise ValueError("unknown contract action")
                except KeyError:
                    self._send_json({"error": "contract_not_found"}, HTTPStatus.NOT_FOUND)
                    return
                except (ValueError, json.JSONDecodeError) as error:
                    self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                    return
                self._send_json(result)
                return
            execution_action = self._execution_action(parsed.path)
            if execution_action:
                execution_id, action = execution_action
                if action != "evidence":
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                try:
                    self._send_json(state.record_evidence(execution_id, self._read_json()), HTTPStatus.CREATED)
                except KeyError:
                    self._send_json({"error": "execution_not_found"}, HTTPStatus.NOT_FOUND)
                except (ValueError, json.JSONDecodeError) as error:
                    self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            if parsed.path == "/api/harness/start":
                self._start_harness()
                return
            if parsed.path == "/api/explore/sessions":
                self._send_json(state.explore.create_session(), HTTPStatus.CREATED)
                return
            if parsed.path == "/api/scenarios":
                self._capture_scenario()
                return
            if parsed.path == "/api/scenarios/compare":
                self._compare_scenarios()
                return
            tool_name = self._mcp_tool_name(parsed.path)
            if tool_name:
                self._execute_mcp_tool(tool_name)
                return
            if parsed.path == "/api/mcp/proposals/ack":
                self._acknowledge_mcp_proposals()
                return
            session_id = self._explore_message_session_id(parsed.path)
            if session_id:
                self._send_explore_message(session_id)
                return
            if parsed.path.startswith("/api/harness/v1/"):
                self._proxy_harness("POST", parsed)
                return
            if parsed.path != "/api/observations":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            try:
                payload = self._read_json(max_bytes=64_000)
                if not isinstance(payload, dict):
                    raise ValueError("body must be a JSON object")
                observation = state.add_observation(payload)
            except (ValueError, json.JSONDecodeError) as error:
                self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            self._send_json(observation, HTTPStatus.CREATED)

        def do_PUT(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/harness/v1/"):
                self._proxy_harness("PUT", parsed)
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_DELETE(self) -> None:
            path = urlparse(self.path).path
            session_id = self._explore_session_id(path)
            if session_id:
                try:
                    state.explore.delete_session(session_id)
                except KeyError as error:
                    self._send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
                    return
                self._send_json({"deleted": True})
                return
            if path != "/api/harness":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if state.harness_host is not None:
                state.harness_host.stop()
                state.set_fixture(state.harness_host.project_dir)
            self._send_json({"running": False})

        def _send_explore_message(self, session_id: str) -> None:
            try:
                payload = self._read_json(max_bytes=128_000)
                response = state.explore.send_message(
                    session_id,
                    str(payload.get("message", "")),
                    payload.get("context") if isinstance(payload.get("context"), dict) else {},
                )
            except KeyError as error:
                self._send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
                return
            except (ValueError, json.JSONDecodeError) as error:
                self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            except RuntimeError as error:
                self._send_json({"error": str(error)}, HTTPStatus.BAD_GATEWAY)
                return
            self._send_json(response)

        def _capture_scenario(self) -> None:
            try:
                payload = self._read_json()
                scenario = state.scenarios.capture(payload)
            except (ValueError, json.JSONDecodeError) as error:
                self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            self._send_json(scenario, HTTPStatus.CREATED)

        def _compare_scenarios(self) -> None:
            try:
                payload = self._read_json(max_bytes=16_000)
                if not isinstance(payload, dict):
                    raise ValueError("body must be a JSON object")
                left = state.scenarios.get(payload.get("left_id"))
                right = state.scenarios.get(payload.get("right_id"))
                comparison = state.scenarios.compare(
                    payload.get("left_id"), payload.get("right_id")
                )
                comparison["impact"] = state.contract_impact.analyze(
                    left["snapshot"], right["snapshot"], state.graph()
                )
            except KeyError as error:
                self._send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
                return
            except (ValueError, json.JSONDecodeError) as error:
                self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            self._send_json(comparison)

        def _execute_mcp_tool(self, tool_name: str) -> None:
            try:
                payload = self._read_json(max_bytes=128_000)
                arguments = payload.get("arguments", {})
                if not isinstance(arguments, dict):
                    raise ValueError("arguments must be a JSON object")
                gateway = state.contract_tools if tool_name.startswith("Contract") else state.graph_tools
                result = gateway.execute(tool_name, arguments)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            self._send_json(result)

        def _acknowledge_mcp_proposals(self) -> None:
            try:
                payload = self._read_json(max_bytes=16_000)
                revisions = payload.get("revisions")
                if not isinstance(revisions, list):
                    raise ValueError("revisions must be an array of integers")
                result = state.graph_tools.acknowledge_proposals(revisions)
            except (ValueError, json.JSONDecodeError) as error:
                self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            self._send_json(result)

        @staticmethod
        def _contract_id(path: str) -> str | None:
            segments = path.strip("/").split("/")
            if len(segments) == 3 and segments[:2] == ["api", "contracts"]:
                return segments[2]
            if len(segments) == 3 and segments[:2] == ["api", "executions"]:
                return f"execution:{segments[2]}"
            return None

        @staticmethod
        def _contract_action(path: str) -> tuple[str, str] | None:
            segments = path.strip("/").split("/")
            if len(segments) == 4 and segments[:2] == ["api", "contracts"]:
                return segments[2], segments[3]
            return None

        @staticmethod
        def _execution_action(path: str) -> tuple[str, str] | None:
            segments = path.strip("/").split("/")
            if len(segments) == 4 and segments[:2] == ["api", "executions"]:
                return segments[2], segments[3]
            return None

        @staticmethod
        def _mcp_tool_name(path: str) -> str | None:
            segments = path.strip("/").split("/")
            return segments[3] if len(segments) == 4 and segments[:3] == ["api", "mcp", "tools"] else None

        @staticmethod
        def _explore_session_id(path: str) -> str | None:
            segments = path.strip("/").split("/")
            return segments[3] if len(segments) == 4 and segments[:3] == ["api", "explore", "sessions"] else None

        @staticmethod
        def _explore_message_session_id(path: str) -> str | None:
            segments = path.strip("/").split("/")
            return segments[3] if len(segments) == 5 and segments[:3] == ["api", "explore", "sessions"] and segments[4] == "messages" else None

        @staticmethod
        def _scenario_id(path: str) -> str | None:
            segments = path.strip("/").split("/")
            return segments[2] if len(segments) == 3 and segments[:2] == ["api", "scenarios"] else None

        def _start_harness(self) -> None:
            if state.harness_host is None:
                self._send_json({"error": "harness_not_configured"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            if not state.project_selected:
                self._send_json(
                    {"error": "project_not_selected", "detail": "select a project folder first"},
                    HTTPStatus.CONFLICT,
                )
                return
            try:
                payload = self._read_json()
                status = state.harness_host.start(
                    task=str(payload.get("task", "Graph Lab mission")),
                    branch=str(payload.get("branch", "")),
                    mode=str(payload.get("mode", "full")),
                    resume=bool(payload.get("resume", False)),
                    no_grill=bool(payload.get("no_grill", False)),
                )
                state.set_fixture(Path(str(status["project_dir"])))
            except (HarnessHostError, ValueError, json.JSONDecodeError) as error:
                self._send_json({"error": "harness_start_failed", "detail": str(error)}, HTTPStatus.BAD_GATEWAY)
                return
            self._send_json(status, HTTPStatus.CREATED)

        def _select_project(self) -> None:
            try:
                payload = self._read_json(max_bytes=16_000)
                raw_path = payload.get("path")
                if not isinstance(raw_path, str) or not raw_path.strip():
                    raise ValueError("project path must not be empty")
                status = state.select_project(Path(raw_path.strip()))
            except (HarnessHostError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
                self._send_json(
                    {"error": "project_selection_failed", "detail": str(error)},
                    HTTPStatus.BAD_REQUEST,
                )
                return
            self._send_json(status)

        def _proxy_harness(self, method: str, parsed) -> None:  # noqa: ANN001
            if state.harness_host is None:
                self._send_json({"error": "harness_not_configured"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            body = None
            if method in {"POST", "PUT"}:
                try:
                    body = self._read_body()
                except ValueError as error:
                    self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                    return
            worker_path = "/api" + parsed.path.removeprefix("/api/harness")
            if parsed.query:
                worker_path += "?" + parsed.query
            status, content_type, response_body = state.harness_host.request(method, worker_path, body)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

        def _read_json(self, *, max_bytes: int = MAX_REQUEST_BYTES) -> dict[str, Any]:
            payload = json.loads(self._read_body(max_bytes=max_bytes))
            if not isinstance(payload, dict):
                raise ValueError("body must be a JSON object")
            return payload

        def _read_body(self, *, max_bytes: int = MAX_REQUEST_BYTES) -> bytes:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > max_bytes:
                raise ValueError("invalid request size")
            return self.rfile.read(content_length)

        def _serve_static(self, request_path: str) -> None:
            relative_path = "index.html" if request_path == "/" else request_path.lstrip("/")
            candidate = (STATIC_ROOT / relative_path).resolve()
            if STATIC_ROOT.resolve() not in candidate.parents:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if not candidate.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_types = {
                ".css": "text/css; charset=utf-8",
                ".html": "text/html; charset=utf-8",
                ".js": "text/javascript; charset=utf-8",
            }
            body = candidate.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_types.get(candidate.suffix, "application/octet-stream"))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return LabRequestHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the HERO graph experiment lab")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--fixture", default=DEFAULT_FIXTURE, type=Path)
    parser.add_argument("--state", default=DEFAULT_STATE, type=Path)
    parser.add_argument("--mission-project", type=Path)
    parser.add_argument("--legacy-harness", action="store_true", help="Enable the deprecated HARNESS bridge")
    parser.add_argument(
        "--explore-provider",
        choices=("fake", "anthropic", "openai", "deepseek", "gemini"),
        default="fake",
    )
    parser.add_argument("--explore-model")
    args = parser.parse_args()

    mission_project = initial_project(args.fixture, args.mission_project)
    harness_host = None
    if args.legacy_harness:
        harness_root = detect_harness_root()
        harness_python = detect_harness_python(harness_root) or Path(sys.executable)
        harness_host = HarnessWorkerHost(
            project_dir=mission_project,
            harness_root=harness_root,
            python_executable=harness_python,
        )
    state = LabState(
        mission_project,
        args.state,
        harness_host,
        project_selected=args.mission_project is not None,
        explore_client=create_model_client(args.explore_provider, args.explore_model),
    )
    server = ThreadingHTTPServer((args.host, args.port), make_handler(state))
    print(f"HERO graph lab: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if harness_host is None:
            server.server_close()
            return
        harness_host.stop()
        server.server_close()


if __name__ == "__main__":
    main()
