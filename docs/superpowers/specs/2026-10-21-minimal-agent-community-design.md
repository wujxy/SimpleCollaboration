# Minimal Agent Community Design

## Purpose

Build the smallest useful peer-agent community: several independent Claude
Code sessions receive the same task, know who their collaborators are, can
message one another directly, and work in the same task workspace. The
community must be able to complete real work, including a ParticleBench run;
it is not an experiment in whether agents invent collaboration without being
told collaboration exists.

This first version establishes the substrate on which later roles or research
policies can be justified. It deliberately does not encode a PI, reviewer,
executor, meeting schedule, action gate, task graph, or scientific workflow.

## Decisions

### Independent sessions, not Claude Code Agent Teams

The runtime launches multiple independent Claude Code sessions. It does not
use Claude Code Agent Teams because that feature defines one session as the
team lead. Independent sessions have their own contexts and can communicate
through Claude Code's native `ListAgents` and `SendMessage` tools without a
lead.

The supported Claude Code version is 2.1.248 or newer on Linux. That version is
the documented floor for same-machine messaging on third-party providers or
with feature-flag fetching disabled, which matches the ParticleBench use case.
The development machine currently has 2.1.299. Cross-session messaging is a
Claude Code capability, not a protocol implemented by this project.

References:

- <https://code.claude.com/docs/en/cross-session-messaging>
- <https://code.claude.com/docs/en/agent-sdk/streaming-vs-single-mode>

### Persistent streaming-input processes

Each member is one long-lived `claude -p` process using streaming JSON input
and output. The parent keeps the member's stdin open after the initial task.
A completed turn therefore makes the member idle rather than destroying its
identity. Claude Code's native inbox can wake an idle member when another
session sends it a message.

The runtime does not use `claude --bg`: that mode delegates lifecycle to a
machine-level daemon and normally moves sessions into isolated worktrees. The
community needs one process tree owned by the harness and one shared task
workspace.

### One shared writable workspace

All members start in the same working directory and observe the same files.
They are told that concurrent edits can conflict and that they should use
messages to coordinate overlapping work. The harness does not assign files or
merge branches. File conflicts and duplicated work remain visible team
failures rather than being hidden by an integration role.

### Collaboration awareness without roles

Every member receives the original task unchanged as its first user message.
The harness appends the same stable collaboration charter to Claude Code's
system prompt. The charter states:

- this is a peer team working on one shared objective;
- every member is responsible for the whole task, not merely a delegated part;
- the deterministic member names and the native `ListAgents` / `SendMessage`
  tools;
- members may investigate, edit, test, propose direction, challenge peers,
  and change their own plan without permission;
- discoveries, failures, objections, plans that may overlap, and consequential
  actions should be communicated when they matter to teammates;
- no member is the default leader and no member controls another member's
  lifecycle.

The charter does not mandate message frequency, consensus, fixed phases,
roles, meetings, or approval.

### ParticleBench owns benchmark policy

SimpleCollaboration is an agent harness, not a benchmark controller.
ParticleBench remains the only owner of:

- the task and generic runtime prompt;
- writable mounts and container isolation;
- wall time and submit budgets;
- `jb submit`, `jb status`, and `jb final-submit` semantics;
- submit serialization, snapshots, feedback, final selection, and grading;
- API proxying and authoritative cost accounting.

The collaboration charter tells members that the workspace and submit budget
are shared team resources and that they should communicate before a
consequential submit. It does not require an elected submitter or unanimous
approval. Every member retains access to the ParticleBench commands. The
harness does not intercept or reimplement them.

## User Interface

The standalone interface is intentionally narrow:

```text
simplecollab run --members 3 --cwd PROJECT [--model MODEL] [--effort LEVEL]
                 [--state-dir DIR] [--resume RUN_ID]
                 [--settle-seconds 5]
```

The task is read from stdin. Standard output is JSONL so a caller can monitor
the run without parsing terminal rendering. Configuration is passed through
explicit command-line arguments and environment variables; credentials are
never copied into run records.

Member count must be at least two. The default team has three homogeneous
members named with a run-specific
prefix, for example `sc-a1b2-member-1`. The unique prefix prevents accidental
addressing of unrelated live Claude sessions. The complete roster appears in
every member's charter.

## Runtime Flow

1. Validate the Claude Code version and arguments.
2. Create a run directory containing only non-secret metadata and logs.
3. Materialize the stable charter and run-local Claude settings. The settings
   set `crossSessionInbound` to `accept`; no user or project settings file is
   modified.
4. Construct every member's immutable launch specification first, then spawn
   them in a tight loop with identical cwd, model, effort, permissions,
   settings, and original task.
5. Keep every stdin open and multiplex each member's stream-json output into
   tagged community events. A member `result` event means that member is idle,
   not that the team is finished.
6. Native Claude Code messaging delivers peer messages and starts turns in
   idle recipients. The runtime neither reads messages to make scientific
   decisions nor routes them through a coordinator.
7. Stop on an external termination request, ParticleBench finalization, hard
   deadline, fatal loss of all members, or standalone quiescence after every
   live member has completed at least one turn and no further activity occurs
   during the configured settle interval, five seconds by default.
8. Close inputs, terminate remaining children as one process group, and write
   the final non-secret member states and exit reason.

In ParticleBench, `jb final-submit` or the framework wall is authoritative;
standalone quiescence is only a fallback for tasks without an external
controller.

## State and Events

The state surface is deliberately small:

```text
<state-dir>/runs/<run-id>/
|-- run.json
|-- charter.md
|-- members.json
|-- events.jsonl
`-- members/
    |-- member-1.stdout.jsonl
    |-- member-1.stderr.log
    `-- ...
```

The standalone default state directory is `.simplecollab`; the ParticleBench
adapter supplies a path under the run's private scratch/state mount.
`members.json` stores member name, Claude session ID, process state, and exit
status. `events.jsonl` contains a tagged copy of lifecycle and Claude
stream-json events. It is observational; agents do not need to read it to
collaborate. Raw credentials, provider headers, and environment dumps are
never persisted.

For resumption, the state directory keeps all member session IDs. A resumed
community restarts every recoverable member with its own Claude session and
delivers the external resume note to all members. A failed individual member
is recorded; surviving members continue. The runtime fails only if it cannot
start any member or all members are lost.

## ParticleBench Adapter

The package exposes an out-of-tree `jbench.agents` entry point named
`simple-collaboration`. The adapter:

- accepts ParticleBench's prompt and passes it unchanged to the community
  runtime;
- launches the runtime once inside the existing ParticleBench container, so
  all Claude children share the same `/work`, `/jb`, proxy, and process group;
- inherits ParticleBench's configured model, effort, credentials, base URL,
  permission mode, and mounted Claude state;
- classifies tagged child events for progress, outage, refusal, and exit;
- aggregates all member transcripts for trajectory and fallback token usage;
- records each member's identity in the community event stream;
- stops the full process tree when ParticleBench stops the arm.

The adapter adds no benchmark prompt text. The collaboration charter is part
of the tested agent harness's stable system behavior, analogous to an agent
CLI's own system instructions.

## Failure Handling

- **One member fails:** publish the failure event and continue with the other
  members.
- **All members fail or fail to start:** exit nonzero with a concise reason.
- **Malformed child output:** preserve the raw line as a tagged diagnostic;
  do not crash healthy members.
- **Peer messaging unavailable:** fail startup rather than silently running
  several isolated solo agents.
- **Concurrent file edits:** do not auto-merge or roll back. Preserve the
  visible workspace and event evidence.
- **Signal or wall stop:** forward termination to the child process group and
  bound cleanup time.
- **Secrets:** inherit them only in child environments and redact configured
  secret values from persisted stderr and events.

## Implementation Shape

The runtime and ParticleBench adapter are Python so the adapter can implement
ParticleBench's Python plugin protocol directly without a second bridge. The
runtime itself uses only the standard library. A small `package.json` provides
the project-required commands:

- `npm run dev` starts the Python module;
- `npm test` runs the test suite;
- `npm run typecheck` runs Python static checking through the declared npm
  development tool.

This mixed command surface is smaller than a Node runtime plus a separate
Python adapter and keeps ParticleBench integration in one process.

## Tests and Acceptance

All behavior tests use a fake `claude` executable; they do not call a model.
The minimum suite proves:

1. N members launch with distinct names, identical task bytes, one roster,
   one charter, and one cwd.
2. The runtime uses streaming input, keeps member inputs open, and treats a
   member result as idle rather than team completion.
3. Tagged output remains valid JSONL when members write concurrently.
4. One failed member does not stop healthy members; loss of all members does.
5. signals and deadlines stop the entire owned process tree.
6. run records contain no configured test secret.
7. resume maps each stored member to its own session ID.
8. the ParticleBench adapter passes the framework prompt unchanged, preserves
   the framework environment and mounts, and exposes aggregate member events.
9. no code path creates roles, assigns tasks, elects a leader, intercepts
   submit, or waits for member approval.

After unit and adapter contract tests, one explicit real-CLI smoke test should
start two low-budget members on a disposable local task and verify mutual
discovery and one delivered message. It must be opt-in because it consumes API
tokens. A ParticleBench behavior run is a later acceptance test, not part of
the unit suite.

## Explicit Non-goals

- scientific roles or role-specific prompts;
- a shared task database or research-state schema;
- forced debate, review, consensus, or stage transitions;
- automatic decomposition or load balancing;
- private worktrees, merge arbitration, or a designated integrator;
- a custom mailbox, message parser, or meeting service;
- judging whether an agent's scientific decision is correct;
- changing ParticleBench task, submit, budget, or grading semantics.
