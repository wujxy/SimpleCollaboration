from __future__ import annotations


def member_names(run_id: str, count: int) -> tuple[str, ...]:
    if count < 2:
        raise ValueError("a community requires at least two members")
    prefix = "".join(ch for ch in run_id.lower() if ch.isalnum())[:8]
    if not prefix:
        raise ValueError("run id must contain a letter or digit")
    return tuple(f"sc-{prefix}-member-{index}" for index in range(1, count + 1))


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
