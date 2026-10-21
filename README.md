# SimpleCollaboration

SimpleCollaboration starts a small community of independent Claude Code sessions in one shared workspace. Every member receives the same task and the same short collaboration charter. Members discover and contact peers through Claude Code's native `ListAgents` and `SendMessage` tools.

The harness supplies process lifecycle and communication awareness only. It has no PI, leader, fixed roles, task dispatcher, meeting gate, merge role, or submit gate. Every member remains responsible for the shared objective and may use the workspace's own tools, including ParticleBench's submit interface.

## Setup

Requires Python 3.10+ and Claude Code 2.1.248+.

```sh
npm install
python -m pip install -e .
```

## Standalone

```sh
printf '%s\n' 'Inspect this project and improve it.' |
  npm run dev -- --members 3 --cwd /path/to/project
```

All members share `--cwd`. Run state, member session IDs, and the multiplexed event stream are stored under `.simplecollab/runs/` unless `--state-dir` is given.

## ParticleBench

Install this package in the same Python environment as ParticleBench, then verify discovery and the image CLI:

```sh
jb launch --agent simple-collaboration --model kimi-k3 --task tasks/jmrb --check
```

The adapter reuses ParticleBench's container, prompt, proxy/accounting, wall clock, budgets, process-group cleanup, verification, grading, and submit rules. It only replaces the single Claude process with three persistent peer sessions in the same container and writable world.
