from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class HarnessHostError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkerConnection:
    url: str
    token: str
    mission_id: str
    project_dir: str
    branch: str


class HarnessWorkerHost:
    def __init__(
        self,
        *,
        project_dir: Path,
        harness_root: Path,
        python_executable: Path | None = None,
        startup_timeout: float = 30.0,
    ) -> None:
        self.project_dir = project_dir.resolve()
        self.harness_root = harness_root.resolve()
        self.python_executable = (python_executable or Path(sys.executable)).resolve()
        self.startup_timeout = startup_timeout
        self._process: subprocess.Popen[str] | None = None
        self._connection: WorkerConnection | None = None
        self._logs: deque[str] = deque(maxlen=100)
        self._lock = threading.Lock()

    def configure_project(self, project_dir: Path) -> dict[str, object]:
        with self._lock:
            if self._running():
                raise HarnessHostError("stop the active mission before changing project")
            selected = project_dir.resolve()
            if not selected.is_dir():
                raise HarnessHostError(f"mission project not found: {selected}")
            self.project_dir = selected
            self._connection = None
            return self.status()

    def start(
        self,
        *,
        task: str,
        branch: str = "",
        mode: str = "full",
        resume: bool = False,
    ) -> dict[str, object]:
        with self._lock:
            if self._running():
                return self.status()
            self._validate_configuration()
            self._prepare_git_project()
            command = [
                str(self.python_executable),
                "-m",
                "mission_orchestrator.worker",
                "--project",
                str(self.project_dir),
                "--task",
                task or "Graph Lab mission",
                "--mode",
                mode,
            ]
            if branch.strip():
                command.extend(("--branch", branch.strip()))
            if resume:
                command.append("--resume")
            environment = os.environ.copy()
            source_root = str(self.harness_root / "src")
            environment["PYTHONPATH"] = os.pathsep.join(
                item for item in (source_root, environment.get("PYTHONPATH", "")) if item
            )
            self._connection = None
            self._logs.clear()
            self._process = subprocess.Popen(
                command,
                cwd=self.project_dir,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            ready = threading.Event()
            failure: list[str] = []
            threading.Thread(
                target=self._read_worker_stdout,
                args=(self._process.stdout, ready, failure),
                name="graph-lab-harness-stdout",
                daemon=True,
            ).start()
            threading.Thread(
                target=self._drain_worker_stderr,
                args=(self._process.stderr,),
                name="graph-lab-harness-stderr",
                daemon=True,
            ).start()
            if not ready.wait(self.startup_timeout) or self._connection is None:
                detail = failure[0] if failure else "worker startup timed out"
                self._terminate_process()
                raise HarnessHostError(detail)
            return self.status()

    def stop(self) -> None:
        with self._lock:
            self._terminate_process()
            self._connection = None

    def status(self) -> dict[str, object]:
        running = self._running()
        connection = self._connection if running else None
        return {
            "configured": self.harness_root.is_dir() and self.python_executable.is_file(),
            "running": running,
            "mission_id": connection.mission_id if connection else "",
            "project_dir": str(self.project_dir),
            "branch": connection.branch if connection else "",
            "logs": list(self._logs)[-10:],
        }

    def request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
    ) -> tuple[int, str, bytes]:
        connection = self._connection
        if not self._running() or connection is None:
            return _json_response(503, {"error": "harness_worker_unavailable"})
        if not path.startswith("/api/v1/"):
            return _json_response(400, {"error": "invalid_worker_path"})
        request = Request(
            connection.url + path,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {connection.token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=35) as response:
                return (
                    int(response.status),
                    response.headers.get_content_type() or "application/json",
                    response.read(),
                )
        except HTTPError as error:
            return (
                int(error.code),
                error.headers.get_content_type() if error.headers else "application/json",
                error.read(),
            )
        except (ConnectionError, TimeoutError, URLError) as error:
            return _json_response(502, {"error": "harness_worker_error", "detail": str(error)})

    def _read_worker_stdout(
        self,
        stream,
        ready: threading.Event,
        failure: list[str],
    ) -> None:  # noqa: ANN001
        if stream is None:
            failure.append("worker stdout is unavailable")
            ready.set()
            return
        for raw_line in stream:
            line = raw_line.strip()
            if not line:
                continue
            if self._connection is None:
                try:
                    payload = json.loads(line)
                    if payload.get("type") == "harness_worker_ready":
                        self._connection = WorkerConnection(
                            url=str(payload["url"]),
                            token=str(payload["token"]),
                            mission_id=str(payload["mission_id"]),
                            project_dir=str(payload["project_dir"]),
                            branch=str(payload["branch"]),
                        )
                        ready.set()
                        continue
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    pass
            self._logs.append(line)
        if self._connection is None:
            failure.append(self._logs[-1] if self._logs else "worker exited before handshake")
            ready.set()

    def _drain_worker_stderr(self, stream) -> None:  # noqa: ANN001
        if stream is None:
            return
        for line in stream:
            if line.strip():
                self._logs.append(line.strip())

    def _running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _validate_configuration(self) -> None:
        if not (self.harness_root / "src" / "mission_orchestrator").is_dir():
            raise HarnessHostError(f"HARNESS source not found under {self.harness_root}")
        if not self.python_executable.is_file():
            raise HarnessHostError(f"Python executable not found: {self.python_executable}")
        if not self.project_dir.exists():
            raise HarnessHostError(f"mission project not found: {self.project_dir}")

    def _prepare_git_project(self) -> None:
        repository = self._git("rev-parse", "--is-inside-work-tree", check=False)
        if repository.returncode != 0:
            if any(self.project_dir.iterdir()):
                raise HarnessHostError(
                    "selected folder is not a Git repository and is not empty"
                )
            self._git("init", "-b", "main")
        head = self._git("rev-parse", "--verify", "HEAD", check=False)
        if head.returncode != 0:
            self._git(
                "-c",
                "user.name=Graph Lab",
                "-c",
                "user.email=graph-lab@localhost",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "--allow-empty",
                "-m",
                "chore: initialize project",
            )

    def _git(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                ["git", *arguments],
                cwd=self.project_dir,
                text=True,
                capture_output=True,
                check=False,
            )
        except OSError as error:
            raise HarnessHostError(f"could not run Git: {error}") from error
        if check and result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "Git command failed"
            raise HarnessHostError(detail)
        return result

    def _terminate_process(self) -> None:
        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _json_response(status: int, payload: dict[str, object]) -> tuple[int, str, bytes]:
    return status, "application/json", json.dumps(payload).encode("utf-8")