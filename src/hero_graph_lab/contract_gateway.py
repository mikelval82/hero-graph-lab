from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote


CONTRACT_TOOL_SPECS = (
    {
        "name": "ContractListTasks",
        "description": "List approved HARNESS task contracts and their execution state.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "readOnly": True,
    },
    {
        "name": "ContractGetTask",
        "description": "Read one immutable task contract pinned by HARNESS.",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string", "minLength": 1}},
            "required": ["task_id"],
            "additionalProperties": False,
        },
        "readOnly": True,
    },
    {
        "name": "ContractBeginExecution",
        "description": "Acquire the single HARNESS execution lease for a contract task as the MCP actor.",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string", "minLength": 1}},
            "required": ["task_id"],
            "additionalProperties": False,
        },
        "readOnly": False,
    },
    {
        "name": "ContractValidate",
        "description": "Run the common structural verifier for the active execution lease.",
        "inputSchema": {
            "type": "object",
            "properties": {"execution_id": {"type": "string", "minLength": 1}},
            "required": ["execution_id"],
            "additionalProperties": False,
        },
        "readOnly": False,
    },
    {
        "name": "ContractComplete",
        "description": "Complete a leased task only if the common HARNESS verifier passes.",
        "inputSchema": {
            "type": "object",
            "properties": {"execution_id": {"type": "string", "minLength": 1}},
            "required": ["execution_id"],
            "additionalProperties": False,
        },
        "readOnly": False,
    },
    {
        "name": "ContractReportBlocker",
        "description": "Record a bounded blocker and release the active execution lease.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "execution_id": {"type": "string", "minLength": 1},
                "detail": {"type": "string", "minLength": 1, "maxLength": 4000},
            },
            "required": ["execution_id", "detail"],
            "additionalProperties": False,
        },
        "readOnly": False,
    },
    {
        "name": "ContractProposeAmendment",
        "description": "Pause execution and request a reviewed contract amendment in HARNESS.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "execution_id": {"type": "string", "minLength": 1},
                "detail": {"type": "string", "minLength": 1, "maxLength": 4000},
            },
            "required": ["execution_id", "detail"],
            "additionalProperties": False,
        },
        "readOnly": False,
    },
)

CHAT_CONTRACT_TOOL_SPECS = (
    {
        "name": "ContractReadFile",
        "description": "Read one UTF-8 file explicitly owned by the active approved task contract.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "execution_id": {"type": "string", "minLength": 1},
                "path": {"type": "string", "minLength": 1},
            },
            "required": ["execution_id", "path"],
            "additionalProperties": False,
        },
        "readOnly": True,
    },
    {
        "name": "ContractApplyPatch",
        "description": "Apply one unique search/replace in a contract-owned file using its prior SHA-256 hash.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "execution_id": {"type": "string", "minLength": 1},
                "path": {"type": "string", "minLength": 1},
                "expected_sha256": {"type": "string", "minLength": 1},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            "required": ["execution_id", "path", "expected_sha256", "old_text", "new_text"],
            "additionalProperties": False,
        },
        "readOnly": False,
    },
    {
        "name": "ContractRunChecks",
        "description": "Run the repository validation command configured and selected by HARNESS.",
        "inputSchema": {
            "type": "object",
            "properties": {"execution_id": {"type": "string", "minLength": 1}},
            "required": ["execution_id"],
            "additionalProperties": False,
        },
        "readOnly": False,
    },
)


class HarnessContractGateway:
    """Thin MCP-facing adapter over the active HARNESS worker authority."""

    def __init__(
        self,
        harness_host,  # noqa: ANN001
        *,
        actor: str = "mcp",
        include_chat_tools: bool = False,
    ) -> None:
        if actor not in {"mcp", "chat"}:
            raise ValueError(f"unsupported contract actor: {actor}")
        self.harness_host = harness_host
        self.actor = actor
        self.include_chat_tools = include_chat_tools

    def _specs(self) -> tuple[dict[str, Any], ...]:
        return CONTRACT_TOOL_SPECS + (CHAT_CONTRACT_TOOL_SPECS if self.include_chat_tools else ())

    def tool_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "name": spec["name"],
                "description": spec["description"],
                "inputSchema": spec["inputSchema"],
                "annotations": {
                    "readOnlyHint": bool(spec["readOnly"]),
                    "destructiveHint": False,
                    "openWorldHint": False,
                },
            }
            for spec in self._specs()
        ]

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise ValueError("arguments must be a JSON object")
        spec = next((item for item in self._specs() if item["name"] == name), None)
        if spec is None:
            raise ValueError(f"unknown contract tool: {name}")
        self._validate(arguments, spec["inputSchema"])
        if self.harness_host is None:
            raise ValueError("HARNESS worker is unavailable; start or resume a mission first")

        if name == "ContractListTasks":
            return self._request("GET", "/api/v1/contracts/tasks")
        if name == "ContractGetTask":
            task_id = quote(str(arguments["task_id"]), safe="")
            return self._request("GET", f"/api/v1/contracts/tasks/{task_id}")
        if name == "ContractBeginExecution":
            return self._request(
                "POST",
                "/api/v1/contracts/executions",
                {"task_id": arguments["task_id"], "actor": self.actor},
            )
        execution_id = quote(str(arguments["execution_id"]), safe="")
        actions = {
            "ContractReadFile": "read-file",
            "ContractApplyPatch": "apply-patch",
            "ContractRunChecks": "checks",
            "ContractValidate": "validate",
            "ContractComplete": "complete",
            "ContractReportBlocker": "blocker",
            "ContractProposeAmendment": "amendment",
        }
        body = {
            key: value
            for key, value in arguments.items()
            if key != "execution_id"
        }
        return self._request(
            "POST",
            f"/api/v1/contracts/executions/{execution_id}/{actions[name]}",
            body,
        )

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        status, _, response = self.harness_host.request(method, path, body)
        try:
            result = json.loads(response.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ValueError("HARNESS worker returned malformed JSON") from error
        if not isinstance(result, dict):
            raise ValueError("HARNESS worker returned a non-object response")
        if status >= 400:
            detail = result.get("message") or result.get("detail") or result.get("error") or status
            raise ValueError(f"HARNESS contract request failed: {detail}")
        return result

    @staticmethod
    def _validate(arguments: dict[str, Any], schema: dict[str, Any]) -> None:
        properties = schema.get("properties", {})
        unknown = sorted(set(arguments) - properties.keys())
        if unknown:
            raise ValueError(f"unknown argument: {unknown[0]}")
        for key in schema.get("required", []):
            value = arguments.get(key)
            if not isinstance(value, str):
                raise ValueError(f"required string argument missing: {key}")
            minimum = properties[key].get("minLength", 0)
            if len(value) < minimum:
                raise ValueError(f"required string argument missing: {key}")
            maximum = properties[key].get("maxLength")
            if maximum is not None and len(value) > maximum:
                raise ValueError(f"argument is too long: {key}")
