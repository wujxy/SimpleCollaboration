from __future__ import annotations

import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from simplecollab.cli import main


FAKE = Path(__file__).with_name("fake_claude.py")


class CliTests(unittest.TestCase):
    def setUp(self):
        FAKE.chmod(0o755)

    def test_standalone_cli_runs_requested_member_count(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            logs = root / "logs"
            state = root / "state"
            stdout = io.StringIO()
            with patch.dict(os.environ, {"SIMPLECOLLAB_FAKE_LOG_DIR": str(logs)}), patch(
                "sys.stdin", io.StringIO("shared task")
            ), patch("sys.stdout", stdout):
                code = main(
                    [
                        "run",
                        "--members",
                        "2",
                        "--cwd",
                        str(root),
                        "--state-dir",
                        str(state),
                        "--claude",
                        str(FAKE),
                        "--settle-seconds",
                        "0.01",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(len(list(logs.glob("*.input.jsonl"))), 2)
            self.assertEqual(json.loads(stdout.getvalue().splitlines()[-1])["type"], "community_stopped")

    def test_cli_rejects_a_one_member_community(self):
        with tempfile.TemporaryDirectory() as raw, patch("sys.stderr", io.StringIO()) as stderr:
            code = main(["run", "--members", "1", "--cwd", raw])
        self.assertEqual(code, 2)
        self.assertIn("at least two", stderr.getvalue())

    def test_compat_mode_reads_member_sessions_for_resume(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = root / "claude-config"
            state = config / "simplecollab" / "run-community"
            state.mkdir(parents=True)
            (state / "members.json").write_text(
                json.dumps(
                    {
                        "members": [
                            {"name": "sc-communit-member-1", "session_id": "s1"},
                            {"name": "sc-communit-member-2", "session_id": "s2"},
                        ]
                    }
                )
            )
            logs = root / "logs"
            env = {
                "CLAUDE_CONFIG_DIR": str(config),
                "SIMPLECOLLAB_FAKE_LOG_DIR": str(logs),
            }
            with patch.dict(os.environ, env), patch("sys.stdin", io.StringIO("resume note")), patch(
                "sys.stdout", io.StringIO()
            ):
                code = main(
                    [
                        "compat",
                        "--members",
                        "2",
                        "--cwd",
                        str(root),
                        "--claude",
                        str(FAKE),
                        "--resume",
                        "--settle-seconds",
                        "0.01",
                    ]
                )

            self.assertEqual(code, 0)
            for name, expected in (("sc-communit-member-1", "s1"), ("sc-communit-member-2", "s2")):
                argv = json.loads((logs / f"{name}.argv.json").read_text())
                self.assertEqual(argv[argv.index("--resume") + 1], expected)


if __name__ == "__main__":
    unittest.main()
