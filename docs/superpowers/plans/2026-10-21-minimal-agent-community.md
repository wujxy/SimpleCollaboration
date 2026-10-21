# Minimal Agent Community Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable three-member peer Claude Code community with native cross-session messaging and a ParticleBench adapter, without roles or workflow gates.

**Architecture:** A Python parent process owns several persistent `claude -p --input-format stream-json` children in one cwd, feeds each the same task, and multiplexes their native JSON streams. A thin `jbench.agents` plugin subclasses ParticleBench's Claude adapter so ParticleBench keeps its container, proxy, accounting, prompt, submit, and stop behavior while the bound Claude-compatible executable fans out into the community.

**Tech Stack:** Python 3.9+ standard library, Claude Code CLI >= 2.1.248, ParticleBench adapter protocol, unittest, pyright through npm scripts.

## Global Constraints

- Work only in `SimpleCollaboration/`; do not edit secrets, `.env`, user settings, ParticleBench, or production configuration.
- Minimum two members; default exactly three homogeneous members.
- Every member receives the original task bytes as its first user-message content and one identical stable charter through `--append-system-prompt-file`.
- Use native `ListAgents` and `SendMessage`; add no mailbox, team lead, role, task assignment, action gate, or submit interception.
- All members use the same writable cwd and run inside one owned process tree.
- ParticleBench exclusively owns benchmark prompt policy, wall time, submit/final-submit, snapshots, feedback, grading, proxying, and authoritative usage.
- No real model/API call occurs in automated tests.
- Runtime code has no third-party Python dependency.

---

## File Map

- `simplecollab/charter.py`: deterministic member names and stable collaboration charter.
- `simplecollab/runtime.py`: child launch specifications, persistent process lifecycle, JSONL multiplexing, state and cleanup.
- `simplecollab/cli.py`, `simplecollab/__main__.py`: standalone command and Claude-compatible wrapper entry.
- `simplecollab/particlebench.py`: optional out-of-tree ParticleBench adapter.
- `bin/claude`: executable compatibility shim selected by the adapter.
- `tests/fake_claude.py`: deterministic fake streaming Claude process.
- `tests/test_charter.py`, `tests/test_runtime.py`, `tests/test_particlebench.py`: behavior and integration contracts.
- `pyproject.toml`, `package.json`, `pyrightconfig.json`: packaging and required project commands.
- `README.md`: concise operation and non-goals.

### Task 1: Package, Charter, and Launch Contract

**Files:**
- Create: `pyproject.toml`
- Create: `package.json`
- Create: `pyrightconfig.json`
- Create: `simplecollab/__init__.py`
- Create: `simplecollab/charter.py`
- Create: `simplecollab/runtime.py`
- Test: `tests/test_charter.py`

**Interfaces:**
- Produces: `member_names(run_id: str, count: int) -> tuple[str, ...]`.
- Produces: `build_charter(names: tuple[str, ...]) -> str`.
- Produces: `MemberSpec(name: str, argv: tuple[str, ...])` and `build_specs(config: RunConfig, names: tuple[str, ...]) -> tuple[MemberSpec, ...]`.

- [ ] **Step 1: Write failing charter and launch-spec tests**

```python
def test_charter_names_every_peer_without_roles():
    names = member_names("abcd1234", 3)
    text = build_charter(names)
    assert names == ("sc-abcd1234-member-1", "sc-abcd1234-member-2", "sc-abcd1234-member-3")
    assert all(name in text for name in names)
    assert "SendMessage" in text and "ListAgents" in text
    assert "leader" not in text.lower() and "reviewer" not in text.lower()

def test_specs_use_streaming_input_and_one_shared_cwd(tmp_path):
    cfg = RunConfig(cwd=tmp_path, state_dir=tmp_path / "state", claude="claude")
    specs = build_specs(cfg, member_names("abcd1234", 2))
    assert len(specs) == 2
    assert all("stream-json" in spec.argv for spec in specs)
    assert {spec.cwd for spec in specs} == {tmp_path}
```

- [ ] **Step 2: Run `npm install`, then `npm test -- --filter charter`; expect tests to fail because the package does not exist.**

- [ ] **Step 3: Implement the immutable data types and exact charter**

```python
@dataclass(frozen=True)
class RunConfig:
    cwd: Path
    state_dir: Path
    claude: str
    members: int = 3
    settle_seconds: float = 5.0
    model: str | None = None
    effort: str | None = None
    resume: bool = False

@dataclass(frozen=True)
class MemberSpec:
    name: str
    cwd: Path
    argv: tuple[str, ...]
```

`build_specs` must pass `-p`, both input and output as `stream-json`, `--verbose`, `--name`, `--append-system-prompt-file`, and the run-local `--settings` file. It adds the stored member-specific `--resume` ID only during recovery.

- [ ] **Step 4: Run `npm test -- --filter charter`; expect all charter/spec tests to pass.**
- [ ] **Step 5: Commit `feat: define peer community launch contract`.**

### Task 2: Persistent Community Runtime

**Files:**
- Modify: `simplecollab/runtime.py`
- Create: `simplecollab/cli.py`
- Create: `simplecollab/__main__.py`
- Create: `bin/claude`
- Create: `tests/fake_claude.py`
- Create: `tests/test_runtime.py`

**Interfaces:**
- Consumes: `RunConfig`, `MemberSpec`, `member_names`, `build_charter`, `build_specs`.
- Produces: `run(config: RunConfig, task: str, *, output: TextIO) -> int`.
- Produces: `main(argv: Sequence[str] | None = None) -> int`.

- [ ] **Step 1: Write failing fake-process lifecycle tests**

```python
def test_all_members_receive_identical_task_and_remain_until_quiescent(tmp_path):
    result = run_fake(tmp_path, members=3, task="original task\n")
    assert result.returncode == 0
    records = read_member_inputs(result.state)
    assert [row["message"]["content"] for row in records] == ["original task\n"] * 3
    assert result.events.count("member_idle") == 3
    assert result.events[-1]["type"] == "community_stopped"

def test_one_failed_member_does_not_kill_healthy_members(tmp_path):
    result = run_fake(tmp_path, members=3, fail_member=2)
    assert result.returncode == 0
    assert event_for(result, "member-2", "member_failed")
    assert event_for(result, "member-1", "member_idle")
```

Also test concurrent JSONL validity, session-ID persistence, resume arguments, minimum member validation, all-member failure, signal cleanup, stderr redaction, and malformed child lines.

- [ ] **Step 2: Run `npm test -- --filter runtime`; expect failure because `run` and CLI are incomplete.**

- [ ] **Step 3: Implement the minimal runtime**

```python
def run(config: RunConfig, task: str, *, output: TextIO = sys.stdout) -> int:
    run_id = load_or_create_run_id(config)
    names = member_names(run_id, config.members)
    layout = create_layout(config, run_id, names, build_charter(names))
    specs = build_specs(config, names)
    supervisor = CommunitySupervisor(config, layout, specs, output)
    return supervisor.execute(task)
```

Use one `threading.Lock` around stdout/event-file writes. Persist state atomically with a temporary file plus `Path.replace`. Redact values of environment keys containing `KEY`, `TOKEN`, `SECRET`, or `PASSWORD` before storing diagnostics. Treat malformed stdout as a `member_diagnostic` event containing redacted text.

- [ ] **Step 4: Implement `simplecollab run` and Claude-compatible argument translation**

The standalone parser accepts the spec's flags and task on stdin. Compatibility mode accepts the Claude arguments ParticleBench already emits, removes a single community-level `--resume`, converts `--input-format text` to `stream-json`, and passes all remaining model, effort, permission, output, and settings flags to each real Claude child. `bin/claude --help` and `--version` delegate to the next real `claude` executable on `PATH`; normal execution calls `simplecollab.cli.compat_main`.

- [ ] **Step 5: Run `npm test -- --filter runtime`; expect all runtime tests to pass.**
- [ ] **Step 6: Commit `feat: run persistent peer Claude sessions`.**

### Task 3: ParticleBench Plugin

**Files:**
- Modify: `pyproject.toml`
- Create: `simplecollab/particlebench.py`
- Create: `tests/test_particlebench.py`

**Interfaces:**
- Produces: entry point `simple-collaboration = simplecollab.particlebench:CommunityArm` in group `jbench.agents`.
- Produces: `CommunityArm`, a narrow subclass of `jbench.agents.terminal.TerminalArm`.

- [ ] **Step 1: Write failing plugin tests with the local ParticleBench checkout on `PYTHONPATH`**

```python
def test_adapter_is_registered_and_uses_community_wrapper():
    assert registered()["simple-collaboration"].endswith(":CommunityArm")
    arm = CommunityArm(model="kimi-k3", settings=fixture_settings)
    assert arm.adapter == "simple-collaboration"
    assert arm.name == "community"
    assert arm.claude_binary.name == "claude"

def test_inherited_parsers_aggregate_all_member_transcripts(tmp_path):
    write_two_claude_transcripts(tmp_path)
    assert sum(row["output"] for row in CommunityArm.read_usage(tmp_path)) == 30
```

Also assert start delivers ParticleBench's prompt unchanged to compatibility stdin, stop owns the complete process group, the adapter rejects an unsupported external Claude-binary override, and inherited classification recognizes nested members' raw Claude events.

- [ ] **Step 2: Run `npm test -- --filter particlebench`; expect failure because the entry point and adapter do not exist.**

- [ ] **Step 3: Implement the minimal adapter**

```python
class CommunityArm(TerminalArm):
    adapter = "simple-collaboration"
    name = "community"

    def configure(self, model, settings):
        settings = dict(settings or {})
        if settings.get("claude_binary") not in (None, "image"):
            raise ValueError("simple-collaboration v1 requires the image Claude binary")
        settings["claude_binary"] = WRAPPER
        super().configure(model, settings)

    def launch_spec(self) -> dict:
        spec = super().launch_spec()
        spec["record"].update(adapter=self.adapter, members=3)
        return spec
```

Reuse `TerminalArm` start/resume/stop, proxy environment, state mount, usage parser, trajectory parser, and exit classification. The wrapper locates the image's real Claude executable by scanning `PATH` while excluding its own resolved path.

- [ ] **Step 4: Run `npm test -- --filter particlebench`; expect all plugin tests to pass.**
- [ ] **Step 5: Commit `feat: expose ParticleBench community adapter`.**

### Task 4: Documentation, Full Verification, and Opt-in Smoke

**Files:**
- Create: `README.md`
- Modify: `docs/superpowers/specs/2026-10-21-minimal-agent-community-design.md` only if implementation-discovered facts require correction.
- Create: `docs/validation/2026-10-21-minimal-agent-community.md`

**Interfaces:**
- Consumes: installed `simplecollab` CLI and `simple-collaboration` ParticleBench entry point.
- Produces: reproducible setup, standalone usage, ParticleBench usage, and validation record.

- [ ] **Step 1: Document installation and the two launch paths**

```text
npm install
python -m pip install -e .
printf '%s\n' 'Inspect this project and improve it.' | npm run dev -- --members 3 --cwd /path/to/project
jb launch --agent simple-collaboration --model kimi-k3 --check
```

State explicitly that all members share one workspace, all may submit, and no leader, merge role, custom mailbox, or submit gate exists.

- [ ] **Step 2: Run `npm test`; expect all tests to pass without API/network access.**
- [ ] **Step 3: Run `npm run typecheck`; expect zero errors.**
- [ ] **Step 4: Run `python -m build` only if the `build` module is already available; otherwise validate with `python -m pip install -e .` and `simplecollab --help`.**
- [ ] **Step 5: Run ParticleBench's adapter discovery and non-network preflight against the local checkout; record exact results.**
- [ ] **Step 6: With explicit real-call authorization already present for this requested test, launch one two-member disposable smoke with the configured low-cost model and a strict short wall/budget. Verify both sessions appear, one native peer message is delivered, and cleanup leaves no live member process. Stop immediately if messaging is unavailable.**
- [ ] **Step 7: Record exact commands, versions, test counts, limitations, and whether the real smoke was run in `docs/validation/2026-10-21-minimal-agent-community.md`.**
- [ ] **Step 8: Run `git diff --check`, `git status --short`, `npm test`, and `npm run typecheck`; then commit `docs: validate minimal agent community`.**
