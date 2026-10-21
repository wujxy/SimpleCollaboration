from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from jbench.agents import ArmSession, RunContext
from jbench.agents.terminal import (
    CLAUDE_MOUNT,
    HOLD_ENV,
    MODEL_ENV,
    PERMISSION_MODE,
    TerminalArm,
    _routed,
    auto_compact_env,
    load_creds,
)
from jbench.sandbox import Bind


SOURCE_MOUNT = "/opt/simplecollab-src"


class CommunityArm(TerminalArm):
    """ParticleBench transport for one peer community process tree."""

    adapter = "simple-collaboration"
    name = "community"
    members = 3

    def launch_spec(self) -> dict:
        spec = super().launch_spec()
        args = list(spec["run_args"])
        args[args.index("coding")] = self.adapter
        spec["run_args"] = args
        spec["record"].update(adapter=self.adapter, members=self.members)
        return spec

    def _launch(self, ctx: RunContext, resume_session, stdin_path, label) -> ArmSession:
        task = cast(Any, ctx.task)
        sandbox = cast(Any, ctx.sandbox)
        api_key = getattr(self, "api_key", None)
        base_url = ctx.api_url(self.base_url)
        binds = ctx.world_binds()
        binds.append(Bind(Path(__file__).resolve().parents[1], SOURCE_MOUNT, "ro"))
        path_env = "/opt/jb/bin:" + ctx.image_path_env
        claude = "claude"
        if self.claude_binary is not None:
            claude = f"{CLAUDE_MOUNT}/claude"
            binds.append(Bind(self.claude_binary, claude, "ro"))
            path_env = f"/opt/jb/bin:{CLAUDE_MOUNT}:" + ctx.image_path_env
        env = {
            "PATH": path_env,
            "PYTHONPATH": SOURCE_MOUNT,
            "CLAUDE_CONFIG_DIR": "/scratch/claude-config",
            "PYTHONPYCACHEPREFIX": "/scratch/pycache",
            **auto_compact_env(self.model),
            **({} if self.model is None else HOLD_ENV),
            **(
                _routed(load_creds(), ctx)
                if self.model is None
                else {
                    "ANTHROPIC_AUTH_TOKEN": api_key,
                    "ANTHROPIC_BASE_URL": base_url,
                    **{key: self.model for key in MODEL_ENV},
                }
            ),
        }
        command = [
            "python3",
            "-m",
            "simplecollab",
            "compat",
            "--members",
            str(self.members),
            "--cwd",
            "/work",
            "--claude",
            claude,
            "--permission-mode",
            PERMISSION_MODE,
            *([] if self.model is None else ["--model", self.model]),
            *([] if self.effort is None else ["--effort", self.effort]),
            *([] if resume_session is None else ["--resume"]),
        ]
        argv = sandbox.build_argv(
            binds=binds,
            cwd="/work",
            command=command,
            taskset=task.taskset_agent,
            cpus=task.agent_cpus,
            memory=task.agent_memory,
            gpus=getattr(task, "agent_gpus", 0),
        )
        proc = sandbox.spawn(
            argv,
            env,
            stdin_path=stdin_path,
            stdout_path=ctx.trace_path(),
            stderr_path=ctx.stderr_path(),
        )
        return ArmSession(proc=proc, label=label)
