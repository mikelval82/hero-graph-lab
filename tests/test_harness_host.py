from __future__ import annotations

import subprocess
from json import loads
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from hero_graph_lab.harness_host import (
    HarnessHostError,
    HarnessWorkerHost,
    WorkerConnection,
)


HARNESS_ROOT = Path(__file__).parents[2] / "HARNESS"


class HarnessWorkerHostTest(TestCase):
    def test_worker_command_can_skip_grill(self) -> None:
        host = HarnessWorkerHost(project_dir=HARNESS_ROOT, harness_root=HARNESS_ROOT)

        command = host._worker_command(
            task="A mission",
            branch="feature/a-mission",
            mode="full",
            resume=False,
            no_grill=True,
        )

        self.assertIn("--no-grill", command)
        self.assertNotIn("--resume", command)

    def test_mission_worktree_path_is_stable(self) -> None:
        host = HarnessWorkerHost(project_dir=HARNESS_ROOT, harness_root=HARNESS_ROOT)

        first = host._mission_worktree_path(task="A mission", branch="feature/a-mission")
        second = host._mission_worktree_path(task="A mission", branch="feature/a-mission")

        self.assertEqual(first, second)
        self.assertTrue(str(first).startswith("/tmp/hero-graph-lab-mission-"))

    def test_stop_preserves_worker_worktree_for_resume(self) -> None:
        host = HarnessWorkerHost(project_dir=HARNESS_ROOT, harness_root=HARNESS_ROOT)
        host._worker_worktree = Path("/tmp/mission-to-resume")

        with patch.object(host, "_terminate_process") as terminate, patch.object(
            host, "_remove_worker_worktree"
        ) as remove:
            host.stop()

        terminate.assert_called_once()
        remove.assert_not_called()
        self.assertIsNone(host._worker_worktree)

    def test_worker_connection_reset_is_normalized(self) -> None:
        host = HarnessWorkerHost(project_dir=HARNESS_ROOT, harness_root=HARNESS_ROOT)
        host._process = type("RunningProcess", (), {"poll": lambda self: None})()
        host._connection = WorkerConnection(
            url="http://127.0.0.1:1",
            token="hidden",
            mission_id="test:mission",
            project_dir=str(HARNESS_ROOT),
            branch="feature/test",
        )

        with patch(
            "hero_graph_lab.harness_host.urlopen",
            side_effect=ConnectionResetError("worker stopped"),
        ):
            status, content_type, body = host.request("GET", "/api/v1/events")

        self.assertEqual(status, 502)
        self.assertEqual(content_type, "application/json")
        self.assertEqual(loads(body)["error"], "harness_worker_error")

    def test_prepares_empty_folder_as_committed_git_project(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            host = HarnessWorkerHost(project_dir=project, harness_root=HARNESS_ROOT)

            host._prepare_git_project()

            result = subprocess.run(
                ["git", "log", "-1", "--pretty=%s"],
                cwd=project,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual(result.stdout.strip(), "chore: initialize project")

    def test_rejects_non_empty_folder_without_git(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "idea.md").write_text("# Idea\n", encoding="utf-8")
            host = HarnessWorkerHost(project_dir=project, harness_root=HARNESS_ROOT)

            with self.assertRaisesRegex(HarnessHostError, "not a Git repository"):
                host._prepare_git_project()
