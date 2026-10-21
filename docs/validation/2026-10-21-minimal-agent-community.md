# Minimal Agent Community Validation — 2026-10-21

## Automated checks

- `npm test`: 16 tests, no model or network calls.
- `npm run typecheck`: 0 errors, 0 warnings.
- Editable install in a local Python 3.11 venv succeeded with `--no-build-isolation`.
- Installed entry-point discovery returned `simple-collaboration = simplecollab.particlebench:CommunityArm`.
- Adapter tests ran against `/datafs/users/wujxy/agent-sci/particle-lab/ParticleBench` at commit `7c581c0`.

## ParticleBench preflight

Command inputs used the jmrb task at `particle-lab/ParticleBench-tasks/tasks/jmrb`, the existing Claude settings path, the CVMFS agent image, and the existing pilot datasets. No configuration or secret file was modified.

Result:

- adapter: `simple-collaboration`
- model: `kimi-k3`
- image Claude Code: `2.1.285`
- image and CLI checks: passed
- scripted shell tool call: passed
- real model requests: 0

## Live peer transport smoke

A two-member standalone smoke used host Claude Code `2.1.299` and the existing default provider configuration. Both persistent sessions shared one temporary workspace and received the same task.

Observed in the second, cleanup-validating run:

- wall time: 21.5 seconds
- distinct sessions: 2
- `ListAgents` calls: 2
- `SendMessage` calls: 2
- both members created their own `.peer-ok` marker after peer contact
- at least one result was a separately awakened peer-origin turn
- final member states: both `idle`, both child exit codes `0`
- terminal event: `community_stopped`, reason `quiescent`
- no member process remained after exit
- Claude's reported aggregate cost estimate across the three result turns: USD 0.621799

The first smoke exposed a lifecycle defect: a `command_lifecycle: completed` event arriving after `result` changed a member from idle back to running. A regression test was added and the state transition was narrowed so only substantive assistant/thinking or unfinished lifecycle events reopen a member. The second live smoke then exited through the intended quiescence path.

## Interpretation and limits

This validates mechanism, not research quality: independent Claude sessions can discover one another, exchange native messages in both directions, wake on peer work, share files, and terminate as one owned process tree. The live smoke used the host's default `deepseek-flash[1m]`; the ParticleBench `kimi-k3` path was validated without a real model request and still requires a benchmark run.

The smoke also showed the fixed cost clearly: each fresh member's first request read roughly 24k input tokens before useful collaboration began. A three-member benchmark therefore needs to justify parallelism with better decisions or elapsed time; the community harness does not make multi-agent inference cheap by itself.
