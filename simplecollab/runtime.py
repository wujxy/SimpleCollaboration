from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class RunConfig:
    cwd: Path
    state_dir: Path
    claude: str
    members: int = 3
    settle_seconds: float = 5.0
    model: str | None = None
    effort: str | None = None
    permission_mode: str | None = None
    resume_sessions: Mapping[str, str] = field(default_factory=dict)
    extra_argv: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemberSpec:
    name: str
    cwd: Path
    argv: tuple[str, ...]


def build_specs(config: RunConfig, names: tuple[str, ...]) -> tuple[MemberSpec, ...]:
    charter = config.state_dir / "charter.md"
    settings = config.state_dir / "settings.json"
    specs = []
    for name in names:
        argv = [
            config.claude,
            "-p",
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
            "--name",
            name,
            "--append-system-prompt-file",
            str(charter),
            "--settings",
            str(settings),
        ]
        if config.model:
            argv.extend(("--model", config.model))
        if config.effort:
            argv.extend(("--effort", config.effort))
        if config.permission_mode:
            argv.extend(("--permission-mode", config.permission_mode))
        session_id = config.resume_sessions.get(name)
        if session_id:
            argv.extend(("--resume", session_id))
        argv.extend(config.extra_argv)
        specs.append(MemberSpec(name=name, cwd=config.cwd, argv=tuple(argv)))
    return tuple(specs)
