from __future__ import annotations

from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from simplecollab.runtime import RunConfig, run


FAKE = Path(__file__).with_name("fake_claude.py")


@contextmanager
def fake_environment(log_dir: Path, **values: str):
    env = {"SIMPLECOLLAB_FAKE_LOG_DIR": str(log_dir), **values}
    with patch.dict(os.environ, env, clear=False):
        yield


def parsed_lines(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        FAKE.chmod(0o755)

    def config(self, root: Path, *, members: int = 3, resume=None) -> RunConfig:
        state = root / "run-abcd1234"
        state.mkdir()
        return RunConfig(
            cwd=root,
            state_dir=state,
            claude=str(FAKE),
            members=members,
            settle_seconds=0.05,
            resume_sessions=resume or {},
        )

    def test_all_members_receive_identical_task_and_stop_after_quiescence(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            logs = root / "fake-logs"
            output = io.StringIO()
            config = self.config(root)
            with fake_environment(logs):
                code = run(config, "original task\n", output=output)

            events = parsed_lines(output.getvalue())
            inputs = []
            for path in sorted(logs.glob("*.input.jsonl")):
                inputs.extend(parsed_lines(path.read_text(encoding="utf-8")))

            self.assertEqual(code, 0)
            self.assertEqual(len(inputs), 3)
            self.assertEqual(
                [row["message"]["content"] for row in inputs],
                ["original task\n"] * 3,
            )
            self.assertEqual(
                {row["community_member"] for row in events if row["type"] == "result"},
                {"sc-abcd1234-member-1", "sc-abcd1234-member-2", "sc-abcd1234-member-3"},
            )
            self.assertEqual(events[-1]["type"], "community_stopped")
            state = json.loads((config.state_dir / "members.json").read_text())
            self.assertTrue(all(member["session_id"] for member in state["members"]))

    def test_one_failed_member_does_not_stop_healthy_members(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            logs = root / "fake-logs"
            output = io.StringIO()
            config = self.config(root)
            failed = "sc-abcd1234-member-2"
            with fake_environment(logs, SIMPLECOLLAB_FAKE_FAIL=failed):
                code = run(config, "task", output=output)

            events = parsed_lines(output.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(any(
                row["type"] == "member_failed" and row["community_member"] == failed
                for row in events
            ))
            self.assertEqual(sum(row["type"] == "result" for row in events), 2)

    def test_all_failed_members_fail_the_community(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            logs = root / "fake-logs"
            output = io.StringIO()
            config = self.config(root, members=2)
            with fake_environment(logs, SIMPLECOLLAB_FAKE_FAIL="all"):
                code = run(config, "task", output=output)

            self.assertNotEqual(code, 0)
            self.assertEqual(parsed_lines(output.getvalue())[-1]["reason"], "all_members_failed")

    def test_resume_uses_each_members_own_session(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            logs = root / "fake-logs"
            resume = {
                "sc-abcd1234-member-1": "session-one",
                "sc-abcd1234-member-2": "session-two",
            }
            config = self.config(root, members=2, resume=resume)
            with fake_environment(logs):
                self.assertEqual(run(config, "continue", output=io.StringIO()), 0)

            for name, session_id in resume.items():
                argv = json.loads((logs / f"{name}.argv.json").read_text())
                self.assertEqual(argv[argv.index("--resume") + 1], session_id)

    def test_malformed_output_is_diagnostic_and_stderr_is_redacted(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            logs = root / "fake-logs"
            output = io.StringIO()
            config = self.config(root, members=2)
            noisy = "sc-abcd1234-member-1"
            with fake_environment(
                logs,
                SIMPLECOLLAB_FAKE_MALFORMED=noisy,
                SIMPLECOLLAB_FAKE_STDERR=noisy,
                TEST_API_TOKEN="super-secret",
            ):
                self.assertEqual(run(config, "task", output=output), 0)

            events = parsed_lines(output.getvalue())
            self.assertTrue(any(row["type"] == "member_diagnostic" for row in events))
            persisted = (config.state_dir / "events.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("super-secret", persisted)
            self.assertIn("[redacted]", persisted)

    def test_sigterm_stops_all_owned_members(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            logs = root / "fake-logs"
            state = root / "state"
            env = {
                **os.environ,
                "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
                "SIMPLECOLLAB_FAKE_LOG_DIR": str(logs),
                "SIMPLECOLLAB_FAKE_HANG": "1",
            }
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "simplecollab",
                    "run",
                    "--members",
                    "2",
                    "--cwd",
                    str(root),
                    "--state-dir",
                    str(state),
                    "--claude",
                    str(FAKE),
                ],
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert process.stdin is not None
            process.stdin.write("task")
            process.stdin.close()
            deadline = time.monotonic() + 3
            while len(list(logs.glob("*.pid"))) < 2 and time.monotonic() < deadline:
                time.sleep(0.02)
            child_pids = [int(path.read_text()) for path in logs.glob("*.pid")]
            self.assertEqual(len(child_pids), 2)

            process.send_signal(signal.SIGTERM)
            self.assertEqual(process.wait(timeout=3), 143)
            for pid in child_pids:
                with self.assertRaises(ProcessLookupError):
                    os.kill(pid, 0)


if __name__ == "__main__":
    unittest.main()
