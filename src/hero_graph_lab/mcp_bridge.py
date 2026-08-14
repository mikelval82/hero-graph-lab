from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


DEFAULT_GRAPH_LAB_URL = "http://127.0.0.1:8765"
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


class GraphLabConnectionError(RuntimeError):
    pass


class GraphLabClient:
    def __init__(self, base_url: str = DEFAULT_GRAPH_LAB_URL, *, timeout: float = 30.0) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in LOOPBACK_HOSTS:
            raise ValueError("Graph Lab MCP only accepts a loopback HTTP URL")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def tools(self) -> dict[str, Any]:
        return self._request("GET", "/api/mcp/tools")

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise ValueError("arguments must be a JSON object")
        return self._request(
            "POST",
            f"/api/mcp/tools/{quote(name, safe='')}",
            {"arguments": arguments},
        )

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json"} if data is not None else {},
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.load(response)
        except HTTPError as error:
            try:
                detail = json.load(error).get("error", error.reason)
            except (AttributeError, json.JSONDecodeError):
                detail = error.reason
            raise GraphLabConnectionError(f"Graph Lab rejected the tool call: {detail}") from error
        except (OSError, URLError) as error:
            raise GraphLabConnectionError(
                f"Graph Lab is unavailable at {self.base_url}; start the web server and try again"
            ) from error
        if not isinstance(result, dict):
            raise GraphLabConnectionError("Graph Lab returned a malformed response")
        return result
