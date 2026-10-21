# Concise Team Charter Design

## Goal

Replace the current policy-style community charter with one short, declarative
description of the team's identity, culture, and communication channels.

## Charter

The generated charter will say:

> You are a research team of {count} agents sharing one research goal and
> responsibility for its outcome. The members are: {roster}. The team organizes
> and divides its own work, shares findings, questions, plans, failures, and
> disagreements, and helps each member avoid getting trapped in a local optimum.
> Research is open within the team: concerns are discussed, messages are
> answered, and members help one another move the work forward. ListAgents shows
> the team and its current status; SendMessage is the direct communication
> channel between members. The problem belongs to the whole team, and the team
> solves it together.

The charter will also describe one piece of team etiquette: when a teammate
speaks to a member, that member responds so the teammate knows the message was
received and understands the member's view. This is social awareness, not a
message-state protocol: the charter defines no reply format, deadline, or fixed
set of responses.

## Scope

Only the generated charter and its focused tests change. The runtime, member
permissions, messaging transport, process lifecycle, and ParticleBench adapter
remain unchanged. The charter introduces no leader, fixed role, approval gate,
mandatory assignment, or meeting workflow.

## Verification

Tests will assert that the charter includes the generated member count and
roster, names `ListAgents` and `SendMessage`, and describes self-organization,
open research, answered messages, mutual help, and shared ownership. Existing
tests will also assert that a teammate can tell both that a message was received
and what the recipient thinks. Existing tests and type checking must continue
to pass.
