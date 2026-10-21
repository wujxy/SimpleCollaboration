from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import uuid

from .runtime import RunConfig, run


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="simplecollab")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "compat"):
        command = subparsers.add_parser(name)
        command.add_argument("--members", type=int, default=3)
        command.add_argument("--cwd", type=Path, default=Path.cwd())
        command.add_argument("--claude", default="claude")
        command.add_argument("--model")
        command.add_argument("--effort", choices=("low", "medium", "high", "xhigh", "max"))
        command.add_argument("--permission-mode")
        command.add_argument("--settle-seconds", type=float, default=5.0)
    standalone = subparsers.choices["run"]
    standalone.add_argument("--state-dir", type=Path)
    compatible = subparsers.choices["compat"]
    compatible.add_argument("--resume", action="store_true")
    compatible.add_argument("--child-arg", action="append", default=[])
    return parser


def _resume_sessions(path: Path) -> dict[str, str]:
    try:
        data = json.loads((path / "members.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {
        str(row["name"]): str(row["session_id"])
        for row in data.get("members", [])
        if isinstance(row, dict) and row.get("name") and row.get("session_id")
    }


def _config(args: argparse.Namespace) -> RunConfig:
    cwd = args.cwd.expanduser().resolve()
    if not cwd.is_dir():
        raise ValueError(f"working directory does not exist: {cwd}")
    if args.members < 2:
        raise ValueError("a community requires at least two members")
    if args.settle_seconds < 0:
        raise ValueError("settle seconds cannot be negative")
    if args.command == "compat":
        config_root = os.environ.get("CLAUDE_CONFIG_DIR")
        if not config_root:
            raise ValueError("compat mode requires CLAUDE_CONFIG_DIR")
        state_dir = Path(config_root) / "simplecollab" / "run-community"
        resume = _resume_sessions(state_dir) if args.resume else {}
        extra = tuple(value for item in args.child_arg for value in ("--" + item).splitlines())
    else:
        state_dir = args.state_dir or cwd / ".simplecollab" / "runs" / f"run-{uuid.uuid4().hex[:8]}"
        resume, extra = {}, ()
    return RunConfig(
        cwd=cwd,
        state_dir=state_dir.expanduser().resolve(),
        claude=args.claude,
        members=args.members,
        settle_seconds=args.settle_seconds,
        model=args.model,
        effort=args.effort,
        permission_mode=args.permission_mode,
        resume_sessions=resume,
        extra_argv=extra,
    )


def main(argv=None) -> int:
    try:
        args = _parser().parse_args(argv)
        config = _config(args)
        task = sys.stdin.read()
        if not task.strip():
            raise ValueError("task on stdin cannot be empty")
        return run(config, task)
    except (ValueError, OSError) as exc:
        print(f"simplecollab: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
