# quickdraw-AI — Current Authorized Task

Last updated: 2026-08-29

This file is the canonical answer to **what work is authorized right now**.
It intentionally excludes completed-task history and speculative next tasks.

## Task

Migrate the repository from overlapping monolithic context files to a
hierarchical, selectively loaded documentation system without losing public
project knowledge, registered research values, acceptance evidence, historical
provenance, or the local/private boundary.

Status: **implemented and documentation-verified locally; not committed or
pushed**.

## Current implementation frontier

R3N is complete, committed, and pushed at
`ca66335ce4e413ce7c4c35827d71154a254b850e`. The current task does not authorize
R3O, update 5, extended training, target synchronization, checkpoint/export,
learned-policy evaluation, gradual motion, strategic combat, reflex, or LLM
implementation.

## Allowed scope

- Restructure repository Markdown documentation.
- Create canonical state, task, research, roadmap, decision, evidence, history,
  and reference documents.
- Refocus `ARCH.md` on software architecture.
- Make `AGENTS.md` the sole procedural authority with selective context loading.
- Convert `CONTEXT.md` to a small ignored local router and preserve its complete
  pre-migration content in an ignored local archive.
- Convert `PROJECT_CONTEXT.md` and `TASKS.md` to compatibility indexes.
- Correct README and documentation links needed for navigation.
- Preserve the existing R3N synchronization edits in `PROJECT_CONTEXT.md` and
  `TASKS.md` as current-state input to the migration.

## Explicit non-goals

- No C#, Python, Unity scene/asset, package, schema, model, test, or runtime
  configuration change.
- No research-design, hypothesis, threshold, hyperparameter, seed, reward,
  action, observation, benchmark, or evaluation change.
- No new experiment, expensive Unity validation, generated evidence, or result
  reinterpretation.
- No deletion of local/private history and no publication of private content.
- No commit, push, staging, history rewrite, deployment, or external mutation.
- No selection or implementation of a subsequent research SSNT.

## Acceptance criteria

1. Each information class has one unambiguous canonical owner.
2. `AGENTS.md` retains all general safety and quality gates and defines
   conditional loading; it does not require every Markdown file on every task.
3. `STATE.md`, `TASK.md`, `RESEARCH.md`, `ROADMAP.md`, and the `docs/` archives
   exist and are navigable.
4. The registered research contract retains all exact values and distinguishes
   unregistered future values rather than inventing them.
5. Detailed R3 evidence retains hashes, commits, tests, transition/update
   boundaries, accepted and rejected attempts, limitations, and negative
   evidence.
6. R3N remains the current pushed implementation frontier; extended training
   remains unimplemented.
7. The old universal-authority, blanket-read, and full-mirroring rules are
   explicitly retired.
8. Private/local material remains ignored and the complete old `CONTEXT.md` is
   recoverable locally.
9. Cross-document links resolve and no code/runtime file changes.
10. Documentation-specific Git, diff, line-ending, authority, duplication,
    value, hash, privacy, and reference audits pass.

## Required verification

- Compare the new research specification against the machine-readable contracts
  and the pre-migration current public sections.
- Compare the new evidence archive against every hash/commit/result in the old
  tracked documentation and relevant contract artifacts.
- Search for stale authority, mirroring, blanket-loading, and status claims.
- Validate relative Markdown links and referenced repository paths.
- Inspect the complete documentation diff, `git diff --check`, new-file list,
  line endings, and final `git status`.
- Confirm only authorized Markdown files changed and no commit or push occurred.

## Relevant context

- Procedure: [`AGENTS.md`](AGENTS.md)
- Current truth: [`STATE.md`](STATE.md)
- Registered design: [`RESEARCH.md`](RESEARCH.md)
- Architecture: [`ARCH.md`](ARCH.md)
- Roadmap: [`ROADMAP.md`](ROADMAP.md)
- Migration record: [`docs/history/DOCUMENTATION_MIGRATION_2026-08-29.md`](docs/history/DOCUMENTATION_MIGRATION_2026-08-29.md)
