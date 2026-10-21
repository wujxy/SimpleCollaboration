# Concise Team Charter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the policy-style prompt with the approved short, declarative research-team charter.

**Architecture:** Keep `build_charter()` as the only production interface and change only its returned text. Lock the intended identity, collaboration culture, roster, and native communication tools in the existing focused unit test; runtime and adapter behavior remain untouched.

**Tech Stack:** Python 3.10+, `unittest`, pyright, npm scripts.

## Global Constraints

- Preserve the existing `member_names(run_id: str, count: int) -> tuple[str, ...]` and `build_charter(names: tuple[str, ...]) -> str` interfaces.
- Keep the charter declarative: it describes team identity, culture, and communication channels rather than issuing a sequence of commands.
- Describe responsive communication as team etiquette: a teammate can tell that
  their message was received and understand the recipient's view. Add no reply
  format, deadline, or fixed response categories.
- Add no roles, leader, assignment gate, meeting workflow, runtime behavior, dependency, or configuration.
- Do not modify secrets, `.env`, ParticleBench, or production configuration.

---

### Task 1: Declarative Research-Team Charter

**Files:**
- Modify: `tests/test_charter.py`
- Modify: `simplecollab/charter.py`

**Interfaces:**
- Consumes: `build_charter(names: tuple[str, ...]) -> str`
- Produces: the approved charter string with the member count and roster interpolated.

- [ ] **Step 1: Write the failing test**

Extend `test_charter_names_every_peer_without_roles` with assertions for the approved declarative language:

```python
self.assertIn("research team of 3 agents", text)
self.assertIn("organizes and divides its own work", text)
self.assertIn("Research is open within the team", text)
self.assertIn("messages are answered", text)
self.assertIn("help one another", text)
self.assertIn("problem belongs to the whole team", text)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m unittest tests.test_charter.CharterTests.test_charter_names_every_peer_without_roles -v`

Expected: FAIL because the current charter does not contain `research team of 3 agents`.

- [ ] **Step 3: Implement the minimal charter change**

Replace only `build_charter()`'s returned text with:

```python
def build_charter(names: tuple[str, ...]) -> str:
    roster = ", ".join(names)
    return f"""You are a research team of {len(names)} agents sharing one research goal and responsibility for its outcome.

The members are: {roster}.

The team organizes and divides its own work, shares findings, questions, plans,
failures, and disagreements, and helps each member avoid getting trapped in a
local optimum. Research is open within the team: concerns are discussed,
messages are answered, and members help one another move the work forward.

ListAgents shows the team and its current status; SendMessage is the direct
communication channel between members. The problem belongs to the whole team,
and the team solves it together.
"""
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `python -m unittest tests.test_charter.CharterTests.test_charter_names_every_peer_without_roles -v`

Expected: PASS.

- [ ] **Step 5: Run full verification**

Run: `npm test`

Expected: all tests pass.

Run: `npm run typecheck`

Expected: zero pyright errors.

- [ ] **Step 6: Commit**

```bash
git add simplecollab/charter.py tests/test_charter.py
git commit -m "feat: make community charter team-oriented"
```

- [ ] **Step 7: Restart the authorized benchmark run**

Stop the current short Kimi pilot through ParticleBench. Launch the formal JMRB
run with the same three-member SimpleCollaboration adapter and the DeepSeek
configuration used by the earlier comparison runs, using the task's full-day
wall budget. Verify the new run has three live member sessions, the generated
charter contains the approved declarative text, and the proxy records successful
model responses.

---

### Task 2: Responsive Team Etiquette

**Files:**
- Modify: `tests/test_charter.py`
- Modify: `simplecollab/charter.py`

**Interfaces:**
- Consumes: `build_charter(names: tuple[str, ...]) -> str`
- Produces: the existing charter plus a declarative description of responsive
  teammate communication.

- [ ] **Step 1: Write the failing test**

Add assertions that the charter says a teammate can tell the message was
received and understand the recipient's view, without prescribing fixed reply
categories.

```python
self.assertIn("lets the teammate know the message was received", text)
self.assertIn("understand what the member thinks", text)
self.assertNotIn("accepted, declined", text)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m unittest tests.test_charter.CharterTests.test_charter_names_every_peer_without_roles -v`

Expected: FAIL because the current charter does not contain the responsive
communication language.

- [ ] **Step 3: Implement the minimal charter change**

Add one declarative sentence describing that team members respond when spoken
to so teammates know their messages were received and understand what each
member thinks.

```text
When a teammate speaks to a member, that member responds in a way that lets the
teammate know the message was received and understand what the member thinks.
```

- [ ] **Step 4: Run focused and full verification**

Run the focused unittest, `npm test`, and `npm run typecheck`; all must pass.

- [ ] **Step 5: Commit**

Commit only the charter, focused test, and the two updated design documents.
