# quickdraw-AI — Current Authorized Task

Last updated: 2026-09-04

This file is the canonical answer to **what work is authorized right now**.
It excludes completed-task history and speculative later work.

## Task

Perform a conservative consolidation and maintainability pass on the Python
research acceptance harness, focused on removing duplicated generic execution
and validation logic from milestone-named runners.

Status: **completed and verified on 2026-09-04; uncommitted by design**.

## Outcome

Generic acceptance plumbing and the update-trajectory execution/validation
engine now have single owners in `quickdraw_bdq.acceptance` and
`quickdraw_bdq.update_gate`. All eleven historical runner paths remain in
place as compatibility entry points, while generic source-level runner imports
fell from 23 to zero; the sole remaining runner import is R3N's intentional
R3M historical-oracle binding.

The complete 222-test trainer suite, historical R3L/R3M/R3O artifact replay,
frozen-byte comparison, CLI/syntax/dependency checks, and independent
read-only contract review passed. No contract, schema, evidence record,
original production-core module, or Unity/C# file changed.

## Implementation boundary

- Move genuinely shared hashing, serialization, runtime validation, worker
  orchestration, result writing, and update-gate behavior into reusable
  `quickdraw_bdq` acceptance modules.
- Keep each historical `run_bdq_*` path and CLI as a thin compatibility entry
  point that owns its milestone contract, expectations, and summary.
- Remove runner-to-runner dependencies when the imported behavior is a generic
  capability; retain milestone-specific dependencies only when they express a
  real provenance or validation relationship.
- Audit the core Python trainer and Unity/C# runtime for maintainability, but do
  not refactor either without a clear, behavior-preserving justification.
- Update the acceptance architecture, operating documentation, and direct
  tests for shared infrastructure.

## Acceptance criteria

- Registered research semantics, hyperparameters, schedules, seeds, counts,
  hashes, losses, thresholds, deterministic behavior, checkpoint behavior,
  contracts, schemas, and accepted evidence remain unchanged.
- Existing historical runner paths, arguments, artifact names, result formats,
  and failure behavior remain compatible.
- Representative historical boundaries and malformed-contract failures remain
  exact, and the complete relevant Python test suite passes.
- Contract, schema, evidence, and original core-module byte hashes match the
  pre-refactor baseline.
- An independent read-only contract review finds no unresolved substantive
  drift, provenance damage, weakened tests, or abstraction overreach.
- Final documentation and repository status accurately describe the result.

## Constraints

Do not change C# runtime behavior, research conclusions, or frozen historical
artifacts. Do not weaken tests or tolerances. Do not introduce a generalized
framework larger than the duplicated mechanisms it replaces. Do not commit or
push.

The verified research frontier remains R3P; this maintainability task does not
authorize a Unity rollout, transition 10,017, optimizer update 6, target
synchronization, extended training, export, or a new effectiveness claim.
