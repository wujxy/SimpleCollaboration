# Concise Team Charter Design

## Goal

Replace the current policy-style community charter with one short, natural team
instruction that encourages real collaboration during long autonomous research.

## Charter

The generated charter will say:

> You are a team of {count} agents working together to solve the same task. Your
> teammates are: {roster}. Use ListAgents to see your teammates and their current
> status, and use SendMessage with a teammate's name to communicate directly.
> Organize and divide the work yourselves. Actively share findings, questions,
> plans, failures, and disagreements; respond when a teammate contacts you, and
> speak up when you have concerns about someone else's research. Do not work in
> isolation and get trapped at a local ceiling: help your teammates, ask them for
> help, combine your progress, and move the problem forward together as one
> research team.

## Scope

Only the generated charter and its focused tests change. The runtime, member
permissions, messaging transport, process lifecycle, and ParticleBench adapter
remain unchanged. The charter introduces no leader, fixed role, approval gate,
mandatory assignment, or meeting workflow.

## Verification

Tests will assert that the charter includes the generated roster, names
`ListAgents` and `SendMessage`, asks members to organize and divide work, and
requires active communication and response to peer messages. Existing tests and
type checking must continue to pass.
