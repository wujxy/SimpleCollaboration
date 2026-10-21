from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from types import FrameType
from typing import Any, Callable, IO, Mapping, TextIO

from .charter import build_charter, member_names


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


@dataclass(frozen=True)
class MemberSpec:
    name: str
    cwd: Path
    argv: tuple[str, ...]


@dataclass
class _Member:
    spec: MemberSpec
    process: subprocess.Popen[str]
    state: str = "starting"
    session_id: str | None = None
    exit_code: int | None = None


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
        specs.append(MemberSpec(name=name, cwd=config.cwd, argv=tuple(argv)))
    return tuple(specs)


class _Events:
    def __init__(self, path: Path, output: TextIO, secrets: tuple[str, ...]):
        self._path = path
        self._output = output
        self._secrets = secrets
        self._lock = threading.Lock()

    def redact(self, text: str) -> str:
        for value in self._secrets:
            text = text.replace(value, "[redacted]")
        return text

    def emit(self, event: dict) -> None:
        encoded = self.redact(json.dumps(event, ensure_ascii=False, sort_keys=True))
        with self._lock:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(encoded + "\n")
            self._output.write(encoded + "\n")
            self._output.flush()


def _secret_values(env: Mapping[str, str]) -> tuple[str, ...]:
    markers = ("KEY", "TOKEN", "SECRET", "PASSWORD")
    return tuple(
        value
        for key, value in env.items()
        if value and any(marker in key.upper() for marker in markers)
    )


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _input_message(task: str) -> str:
    return json.dumps(
        {
            "type": "user",
            "message": {"role": "user", "content": task},
            "parent_tool_use_id": None,
        },
        ensure_ascii=False,
    ) + "\n"


def _event_state(current: str, event: Mapping[str, object]) -> str:
    kind = event.get("type")
    if kind == "result":
        return "idle"
    if kind == "assistant" or (
        kind == "system" and event.get("subtype") == "thinking_tokens"
    ):
        return "running"
    if kind == "command_lifecycle" and event.get("state") != "completed":
        return "running"
    return current


def run(config: RunConfig, task: str, *, output: TextIO | None = None) -> int:
    """Run one peer community until all surviving members are quiescent."""
    output_stream: TextIO = output if output is not None else sys.stdout
    config.state_dir.mkdir(parents=True, exist_ok=True)
    run_token = config.state_dir.name.removeprefix("run-")
    names = member_names(run_token, config.members)
    (config.state_dir / "charter.md").write_text(build_charter(names), encoding="utf-8")
    (config.state_dir / "settings.json").write_text(
        json.dumps({"crossSessionInbound": "accept", "dialogExpiry": "never"}) + "\n",
        encoding="utf-8",
    )
    events_path = config.state_dir / "events.jsonl"
    events_path.touch(exist_ok=True)
    env = {key: value for key, value in os.environ.items()}
    events = _Events(events_path, output_stream, _secret_values(env))
    specs = build_specs(config, names)
    members: dict[str, _Member] = {}
    state_lock = threading.Lock()
    persist_lock = threading.Lock()
    activity = threading.Event()
    stop_requested = threading.Event()
    last_activity = time.monotonic()
    stopping = False
    caught_signal: int | None = None
    previous_handlers: dict[
        int, int | signal.Handlers | Callable[[int, FrameType | None], Any] | None
    ] = {}

    def request_stop(number, _frame) -> None:
        nonlocal caught_signal
        caught_signal = int(number)
        stop_requested.set()
        activity.set()

    if threading.current_thread() is threading.main_thread():
        for number in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[number] = signal.getsignal(number)
            signal.signal(number, request_stop)

    def touch() -> None:
        nonlocal last_activity
        with state_lock:
            last_activity = time.monotonic()
        activity.set()

    def persist() -> None:
        with state_lock:
            rows = [
                {
                    "name": member.spec.name,
                    "state": member.state,
                    "session_id": member.session_id,
                    "exit_code": member.exit_code,
                }
                for member in members.values()
            ]
        with persist_lock:
            _atomic_json(config.state_dir / "members.json", {"members": rows})

    def stdout_reader(member: _Member, stream: IO[str]) -> None:
        nonlocal stopping
        for raw in stream:
            text = raw.rstrip("\n")
            try:
                event = json.loads(text)
                if not isinstance(event, dict):
                    raise ValueError("event is not an object")
                event["community_member"] = member.spec.name
                with state_lock:
                    if event.get("session_id"):
                        member.session_id = str(event["session_id"])
                    member.state = _event_state(member.state, event)
                events.emit(event)
            except (ValueError, TypeError, json.JSONDecodeError):
                events.emit(
                    {
                        "type": "member_diagnostic",
                        "community_member": member.spec.name,
                        "message": text,
                    }
                )
            persist()
            touch()
        code = member.process.wait()
        with state_lock:
            member.exit_code = code
            if code:
                member.state = "failed"
            elif not stopping:
                member.state = "finished"
        if code:
            events.emit(
                {
                    "type": "member_failed",
                    "community_member": member.spec.name,
                    "exit_code": code,
                }
            )
        elif not stopping:
            events.emit({"type": "member_finished", "community_member": member.spec.name})
        persist()
        touch()

    def stderr_reader(member: _Member, stream: IO[str]) -> None:
        for raw in stream:
            events.emit(
                {
                    "type": "member_stderr",
                    "community_member": member.spec.name,
                    "message": raw.rstrip("\n"),
                }
            )
            touch()

    threads: list[threading.Thread] = []
    for spec in specs:
        child_env = dict(env)
        child_env["SIMPLECOLLAB_MEMBER_NAME"] = spec.name
        try:
            process = subprocess.Popen(
                spec.argv,
                cwd=spec.cwd,
                env=child_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            events.emit(
                {
                    "type": "member_failed",
                    "community_member": spec.name,
                    "message": str(exc),
                }
            )
            continue
        member = _Member(spec=spec, process=process)
        members[spec.name] = member
        assert process.stdout is not None and process.stderr is not None
        for target, stream in ((stdout_reader, process.stdout), (stderr_reader, process.stderr)):
            thread = threading.Thread(target=target, args=(member, stream), daemon=True)
            thread.start()
            threads.append(thread)

    if not members:
        persist()
        events.emit({"type": "community_stopped", "reason": "all_members_failed"})
        for number, handler in previous_handlers.items():
            signal.signal(number, handler)
        return 1

    persist()
    message = _input_message(task)
    for member in members.values():
        try:
            assert member.process.stdin is not None
            member.process.stdin.write(message)
            member.process.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    reason = "quiescent"
    code = 0
    while True:
        if stop_requested.is_set():
            reason = "signal"
            code = 128 + (caught_signal or signal.SIGTERM)
            break
        with state_lock:
            current = tuple(member.state for member in members.values())
            quiet_for = time.monotonic() - last_activity
        healthy = tuple(state for state in current if state != "failed")
        if not healthy:
            reason, code = "all_members_failed", 1
            break
        if all(state in {"idle", "finished"} for state in healthy) and quiet_for >= config.settle_seconds:
            break
        activity.wait(timeout=min(0.05, max(0.001, config.settle_seconds)))
        activity.clear()

    stopping = True
    for member in members.values():
        if member.process.stdin is not None:
            try:
                member.process.stdin.close()
            except OSError:
                pass
    for member in members.values():
        try:
            member.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            member.process.terminate()
            try:
                member.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                member.process.kill()
                member.process.wait(timeout=1)
    for thread in threads:
        thread.join(timeout=1)
    persist()
    events.emit({"type": "community_stopped", "reason": reason})
    for number, handler in previous_handlers.items():
        signal.signal(number, handler)
    return code
