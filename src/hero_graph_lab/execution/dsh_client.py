"""Small process bridge for the official DeepSeek Harness CLI (``dsh``).

The bridge deliberately knows nothing about Graph Lab contracts.  It starts a
single official headless DSH session and exposes its lifecycle in neutral
terms, so an execution adapter can supply the contract-specific prompt.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


class DshUnavailableError(RuntimeError):
    """Raised when the official DSH executable is not available."""


class DshConfigurationError(RuntimeError):
    """Raised for a project configuration rejected by the DSH launcher."""


@dataclass
class DshRun:
    execution_id: str
    command: list[str]
    started_at: str
    status: str = "EXECUTING"
    return_code: int | None = None
    output: str = ""
    error: str = ""
    events: list[dict[str, str]] = field(default_factory=list)
    process: subprocess.Popen[str] | None = field(default=None, repr=False)
    finished: threading.Event = field(default_factory=threading.Event, repr=False)


class DshClient:
    """Launch and monitor official ``dsh --profile headless`` sessions."""

    def __init__(
        self,
        project_root: Path,
        *,
        executable: str | None = None,
        popen: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
    ) -> None:
        self.project_root = project_root.resolve()
        self.executable = executable
        self._popen = popen
        self._runs: dict[str, DshRun] = {}
        self._lock = threading.RLock()

    def executable_path(self) -> str | None:
        if self.executable:
            return self.executable if Path(self.executable).is_file() else None
        discovered = shutil.which("dsh")
        if discovered:
            return discovered
        # nvm is commonly loaded only by interactive shells.  Discover its
        # per-user binary without requiring Graph Lab's service process to
        # source shell startup files.
        candidates = sorted(Path.home().glob(".nvm/versions/node/*/bin/dsh"))
        return str(candidates[-1]) if candidates else None

    def available(self) -> bool:
        return self.executable_path() is not None and not self.configuration_error()

    def configuration_error(self) -> str:
        # DSH deliberately rejects DSH_MODEL in a project .env: it must be
        # supplied by the launching environment.  Graph Lab reserves its own
        # prefixed setting and translates it just before launching DSH.
        for filename in (".env", ".env.local"):
            candidate = self.project_root / filename
            if not candidate.is_file():
                continue
            for line in candidate.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("DSH_MODEL="):
                    return f"Move DSH_MODEL from {filename} to HERO_GRAPH_LAB_DSH_MODEL; DSH rejects DSH_MODEL in project dotenv files"
        return ""

    def start(
        self,
        execution_id: str,
        prompt: str,
        *,
        profile: str = "headless",
        environment_overrides: dict[str, str] | None = None,
    ) -> DshRun:
        with self._lock:
            current = self._runs.get(execution_id)
            if current and current.status == "EXECUTING":
                return current
            executable = self.executable_path()
            if executable is None:
                raise DshUnavailableError("DeepSeek DSH is not installed or is not on PATH")
            if configuration_error := self.configuration_error():
                raise DshConfigurationError(configuration_error)

            from hero_graph_lab.explore.clients import load_project_env

            load_project_env(self.project_root)
            environment = os.environ.copy()
            # The npm launcher uses ``#!/usr/bin/env node``.  When Graph Lab
            # was started outside an interactive nvm shell, PATH may still
            # resolve an older system Node.  Keep the DSH launcher and its
            # matching Node runtime together.
            # Do not resolve the launcher symlink here: resolving it enters
            # npm's package directory, whereas the launcher directory is the
            # nvm Node 22 ``bin`` directory that must win PATH lookup.
            dsh_bin = str(Path(executable).parent)
            environment["PATH"] = dsh_bin + os.pathsep + environment.get("PATH", "")
            environment["DSH_CWD"] = str(self.project_root)
            environment.setdefault("DSH_HOME", str(self.project_root / ".graph-lab" / "dsh"))
            environment["DSH_MODEL"] = environment.pop("HERO_GRAPH_LAB_DSH_MODEL", "deepseek-v4-flash")
            environment.update(environment_overrides or {})
            # DSH bootstraps a named profile below this directory but expects
            # its parent hierarchy to exist first.
            (Path(environment["DSH_HOME"]) / "profiles").mkdir(parents=True, exist_ok=True)
            command = [executable, "--profile", profile, prompt]
            process = self._popen(
                command,
                cwd=self.project_root,
                env=environment,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            run = DshRun(execution_id, command, datetime.now(UTC).isoformat(), process=process)
            self._runs[execution_id] = run
            threading.Thread(target=self._collect, args=(run,), daemon=True, name=f"graph-lab-dsh-{execution_id}").start()
            return run

    def status(self, execution_id: str) -> dict[str, object]:
        with self._lock:
            run = self._runs.get(execution_id)
            if run is None:
                return {"execution_id": execution_id, "status": "BLOCKED", "detail": "DSH execution was not started by this Graph Lab process"}
            return {
                "execution_id": execution_id,
                "status": run.status,
                "started_at": run.started_at,
                "return_code": run.return_code,
                "output": run.output[-12_000:],
                "events": list(run.events[-200:]),
                "detail": run.error,
            }

    def cancel(self, execution_id: str) -> None:
        with self._lock:
            run = self._runs.get(execution_id)
            process = run.process if run else None
            if run is None or process is None or run.status != "EXECUTING":
                return
            process.terminate()
            run.status = "BLOCKED"
            run.error = "DeepSeek DSH execution cancelled"

    def wait(self, execution_id: str, timeout: float = 600.0) -> dict[str, object]:
        with self._lock:
            run = self._runs.get(execution_id)
        if run is None:
            return self.status(execution_id)
        if not run.finished.wait(timeout):
            self.cancel(execution_id)
            raise TimeoutError("DeepSeek DSH timed out")
        return self.status(execution_id)

    def prepare_graph_lab_profile(self, *, python_executable: str, graph_lab_url: str) -> str:
        """Create the local DSH profile that exposes Graph Lab MCP tools."""
        dsh_home = self.project_root / ".graph-lab" / "dsh"
        profile = dsh_home / "profiles" / "graph-lab"
        profile.mkdir(parents=True, exist_ok=True)
        files = {
            "package.json": json_dumps({
                "name": "dsh-profile-graph-lab",
                "private": True,
                "dependencies": {"@deepseek-ai/dsh-mcp-client": "0.1.2-rc.1"},
                "dsh": {"profile": {"bundles": ["@deepseek-ai/dsh-base", "@deepseek-ai/dsh-headless"], "patchReload": "startup"}},
            }),
            "pnpm-workspace.yaml": "packages:\n  - .\nnodeLinker: hoisted\nautoInstallPeers: false\n",
            "cordis.yml": "[]\n",
            "cordis.patch.yml": """- insert:
    - id: graph-lab-mcp
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: graph_lab
        transport: stdio
        command: !!js process.env.HERO_GRAPH_LAB_PYTHON
        args: ['-m', 'hero_graph_lab.mcp_server', '--url', !!js process.env.HERO_GRAPH_LAB_URL]
        failOnStartupError: true
""",
        }
        for name, content in files.items():
            target = profile / name
            if not target.is_file() or target.read_text(encoding="utf-8") != content:
                target.write_text(content, encoding="utf-8")
        return "graph-lab"

    def _collect(self, run: DshRun) -> None:
        assert run.process is not None
        readers = [
            threading.Thread(target=self._read_stream, args=(run, run.process.stdout, "agent_message_delta"), daemon=True),
            threading.Thread(target=self._read_stream, args=(run, run.process.stderr, "agent_progress"), daemon=True),
        ]
        for reader in readers:
            reader.start()
        run.process.wait()
        for reader in readers:
            reader.join()
        with self._lock:
            run.return_code = run.process.returncode
            if run.status == "BLOCKED":
                run.finished.set()
                return
            if run.return_code == 0:
                run.status = "VERIFYING"
            else:
                run.status = "BLOCKED"
                run.error = f"DeepSeek DSH exited with status {run.return_code}"
            run.finished.set()

    def _read_stream(self, run: DshRun, stream, event_type: str) -> None:  # noqa: ANN001
        if stream is None:
            return
        for line in stream:
            text = line.rstrip()
            if not text:
                continue
            with self._lock:
                run.output = (run.output + text + "\n")[-24_000:]
                run.events.append({"type": event_type, "text": text})
                del run.events[:-200]


def json_dumps(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, indent=2) + "\n"
