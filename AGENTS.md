# ZERQEN — AGENT OPERATING RULES

## Source of truth

Before changing code, read:

1. `docs/ZERQEN_MASTER_CONTEXT.md` — authoritative product requirements, architecture, invariants, current state, known issues, and next actions.
2. Relevant technical docs under `docs/`.
3. The implementation itself — docs never override executable behavior when describing what is actually implemented.

A new agent must NOT ask the user to re-explain the project when the answer exists in the repository.

## Living-project rule

ZERQEN is a continuously evolving project. The repository documentation is part of the implementation contract.

After every meaningful implementation, bug fix, architecture decision, UX change, risk-rule change, deployment change, or discovered limitation:

- update `docs/ZERQEN_MASTER_CONTEXT.md`;
- update its **Current State**, **Completed Changes**, **Known Issues / Risks**, and **Next Actions** sections as applicable;
- record important decisions with date and rationale;
- preserve historical facts instead of silently rewriting them;
- if a requirement changes, mark the old requirement as superseded and state the new requirement;
- never claim something is implemented until code/tests/deployment evidence supports it.

## Handoff rule

The master context must be sufficient for a fresh coding agent to continue work without relying on chat history.

A handoff must contain, when applicable:

- product mission and UX contract;
- Spot/Futures separation;
- compounding semantics;
- risk invariants;
- AI decision pipeline;
- worker architecture;
- paper/live/testnet boundaries;
- ledger/accounting rules;
- dashboard behavior;
- current implementation status;
- current deployment/commit;
- known bugs and their evidence;
- exact next task;
- verification criteria.

## Safety invariants

Never weaken these without an explicit project decision:

- 8% is a research/compounding objective, never a guaranteed return and never a reason to force a trade.
- Risk controls have authority over AI and target-return logic.
- Spot and Futures are independent engines with independent state, ledgers, risk, and compounding.
- Stop prevents new entries but does not force-close existing positions unless explicitly designed otherwise.
- Paper trading remains paper-only unless a future explicit live-trading gate is implemented and approved.
- Never commit API keys, dashboard tokens, vault keys, database URLs, or other secrets.
- Never treat a successful API response as proof of a long-running worker unless heartbeat/cycle evidence confirms it.
- Never claim deployment/runtime success from source inspection alone.

## Autonomous worker rule

The intended architecture is:

Browser/dashboard
→ Vercel API/control plane
→ persistent Voroa/ZERQEN worker
→ autonomous Spot/Futures cycles
→ market scan → shortlist → AI review → risk gate → paper execution
→ durable ledger/state → truthful dashboard.

The persistent worker must not depend on the user's browser remaining open.

## Verification rule

For every bug fix:

1. identify the exact failure path;
2. reproduce or inspect the relevant code/log evidence;
3. make the smallest safe fix;
4. run relevant tests/static checks;
5. verify deployment state when deployment matters;
6. update the master context with what changed and what remains unverified.

## Documentation priority

If two documents conflict:

- current executable behavior is authoritative for **implemented state**;
- `docs/ZERQEN_MASTER_CONTEXT.md` is authoritative for **product requirements and decisions**;
- older phase/readiness documents are historical unless explicitly marked current.

Do not delete historical documents merely because the project evolved.
