from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
from typing import cast
import unittest


ROOT = Path(__file__).resolve().parents[1]
PB_ROOT = Path(__file__).resolve().parents[5] / "particle-lab" / "ParticleBench"
sys.path.insert(0, str(PB_ROOT))

from jbench.agents.terminal import TerminalArm  # noqa: E402
from jbench.agents import RunContext  # noqa: E402

from simplecollab.particlebench import CommunityArm  # noqa: E402


class _Sandbox:
    def __init__(self):
        self.built: dict = {}
        self.spawned: dict = {}

    def build_argv(self, **kwargs):
        self.built = kwargs
        return ["sandbox", *kwargs["command"]]

    def spawn(self, argv, env, **kwargs):
        self.spawned = {"argv": argv, "env": env, **kwargs}
        return SimpleNamespace(pid=123)


class ParticleBenchTests(unittest.TestCase):
    def test_plugin_entry_point_and_inherited_protocol(self):
        project = (ROOT / "pyproject.toml").read_text()
        self.assertIn('[project.entry-points."jbench.agents"]', project)
        self.assertIn(
            'simple-collaboration = "simplecollab.particlebench:CommunityArm"', project
        )
        self.assertTrue(issubclass(CommunityArm, TerminalArm))
        self.assertIs(CommunityArm.start, TerminalArm.start)
        self.assertIs(CommunityArm.resume, TerminalArm.resume)
        self.assertIs(CommunityArm.stop, TerminalArm.stop)

    def test_launch_keeps_particlebench_ownership_and_runs_community(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            sandbox = _Sandbox()
            task = SimpleNamespace(
                taskset_agent=None,
                agent_cpus=2,
                agent_memory="4G",
                agent_gpus=0,
            )
            ctx = SimpleNamespace(
                task=task,
                sandbox=sandbox,
                image_path_env="/usr/bin",
                world_binds=lambda: [],
                api_url=lambda value: value,
                trace_path=lambda: root / "trace.jsonl",
                stderr_path=lambda: root / "agent.err",
            )
            arm = object.__new__(CommunityArm)
            arm.model = "kimi-k3"
            arm.api_key = "test-key"
            arm.base_url = "https://example.invalid"
            arm.claude_binary = None
            arm.effort = "high"
            stdin = root / "instruction.txt"
            stdin.write_text("particlebench prompt")

            session = arm._launch(
                cast(RunContext, ctx),
                resume_session="previous",
                stdin_path=stdin,
                label="community",
            )

            command = sandbox.built["command"]
            self.assertEqual(command[:3], ["python3", "-m", "simplecollab"])
            self.assertIn("compat", command)
            self.assertEqual(command[command.index("--members") + 1], "3")
            self.assertIn("--resume", command)
            self.assertEqual(sandbox.spawned["stdin_path"], stdin)
            self.assertEqual(sandbox.spawned["stdout_path"], root / "trace.jsonl")
            self.assertEqual(session.label, "community")
            self.assertTrue(any(bind.dst == "/opt/simplecollab-src" for bind in sandbox.built["binds"]))

    def test_inherited_usage_parser_aggregates_member_transcripts(self):
        with tempfile.TemporaryDirectory() as raw:
            run = Path(raw)
            project = run / "scratch" / "claude-config" / "projects" / "-work"
            project.mkdir(parents=True)
            for ordinal, output in ((1, 11), (2, 19)):
                event = {
                    "type": "assistant",
                    "timestamp": f"2026-10-21T00:00:0{ordinal}Z",
                    "uuid": f"u{ordinal}",
                    "message": {
                        "id": f"m{ordinal}",
                        "model": "kimi-k3",
                        "content": [{"type": "text", "text": "ok"}],
                        "usage": {"input_tokens": ordinal, "output_tokens": output},
                    },
                }
                (project / f"member-{ordinal}.jsonl").write_text(json.dumps(event) + "\n")

            usage = CommunityArm.read_usage(run)

            self.assertEqual(len(usage), 2)
            self.assertEqual(sum(row["output"] for row in usage), 30)


if __name__ == "__main__":
    unittest.main()
