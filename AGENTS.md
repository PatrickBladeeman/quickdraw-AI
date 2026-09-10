# Repository Agent Instructions

## Authority and precedence

Applies repository-wide; discover nested AGENTS.md files for the affected scope.
Precedence: system/platform, current user request, nearest applicable AGENTS.md,
authoritative documentation, then source/test conventions. Nested instructions
must not silently weaken repository-wide safety or quality requirements.
This is the sole repository-wide procedural owner; older plans, handoffs, and
generated material cannot override current authority.

Source/tests establish implemented behavior. Machine-readable research contracts
are authoritative executable companions for registered fields. Stop and report
material disagreement that could change the result; do not silently choose a
convenient interpretation.

## Context loading and prerequisite check

For each request, establish its type, explicit authorization, relevant context,
and current Git status before acting. Preserve pre-existing modifications and
untracked files as user-owned. For synchronization/release work, also inspect
branch, upstream, and recent commits. State consequential assumptions and
completion/verification criteria; use a short plan for multi-step work.
Stop for material scope conflicts, unexplained drift, or missing prerequisites.

Normal implementation boot sequence:

1. [STATE.md](STATE.md): current verified truth.
2. [TASK.md](TASK.md): current authorization.
3. Relevant source and tests.
4. Relevant [ARCH.md](ARCH.md) sections: ownership and interfaces.

Retrieve additional context only when it bears on the request:

- [RESEARCH.md](RESEARCH.md) sections for research behavior, reward, observations,
  actions, training, schedules, seeds, fairness, telemetry meaning, evaluation,
  LLM/reflex semantics, thresholds, or hypotheses.
- Relevant [ADR](docs/decisions/README.md) for an architectural decision,
  historically justified invariant, or replacement architecture.
- Specific [evidence](docs/evidence/README.md) when extending, reproducing,
  debugging, or relying on an acceptance claim.
- [Reference](docs/reference/README.md) for setup/operating facts;
  [history](docs/history/README.md) for superseded scope or abandoned designs.

Read relevant sections first; expand large documents only for cross-cutting
consistency. Never require every Markdown file or every relevant large document.
CONTEXT.md is an ignored local router; PROJECT_CONTEXT.md and TASKS.md are tiny
compatibility indexes. None is another source of project truth.

## Authorization boundaries

Explanation, review, audit, and diagnosis authorize read-only investigation.
Change requests authorize in-scope edits and verification, not unrelated cleanup
or modernization. TASK.md owns persistent authorization; roadmap order and
completed acceptance records grant none.
Commits, pushes, force updates, PRs, merges, deployments, publication, messages,
and third-party mutations require explicit user authorization.
Do not broaden access, install unrelated tools, alter machine-wide settings,
or weaken security/validation for convenience. Stop when new authority or a
material product/research decision is required.

## Research-contract protection

Preserve registered hypotheses, thresholds, environments, observation/action/
reward contracts, schedules, seeds, evaluation design, runtime identities,
accepted hashes/results, and frozen artifacts unless an explicit task authorizes
their change. Scientific changes follow [research change control](RESEARCH.md#change-control).
Never lower acceptance thresholds after viewing results or overwrite negative,
null, flaky, failed, or rejected evidence. Label approved exploratory work.
Distinguish software-contract tests, smoke runs, deterministic replay, backend
probes, and local parity from effectiveness, performance, and generalization.
Never launch frozen historical players directly; use complete run-owned copies
and isolate profiling/log output from accepted artifacts.

## Implementation principles

Use the smallest adequate solution within approved scope and existing ownership,
naming, and compatibility conventions. Inspect affected code/tests before design.
Remove only material made obsolete by the task; avoid unrelated refactoring,
dependency upgrades, generated-file refreshes, or speculative abstractions.
Import shared capabilities from their canonical owner, not milestone wrappers.
State the genuinely new acceptance/research claim first. Extend shared execution,
test, and schema mechanisms through contract/configuration data. A bespoke
runner/test/schema stack needs a substantially different contract or execution
boundary; a milestone label, cutoff, or expected value alone is insufficient.
Keep one clear execution path; retain fail-closed validation at plausible
process, network, persistence, input, and research-contract boundaries.
Before changing dependencies/interfaces, inspect locks and compatibility limits.
Preserve exact versions/configuration/seeds/hashes needed for reproduction.

## Verification

Connect each acceptance claim to direct evidence. Start with focused checks,
then broader relevant tests and applicable lint/type/schema/build checks.
Exercise real integration boundaries where unit tests cannot prove the claim;
add practical bug regressions. Inspect warnings and retain failed results.
Do not weaken tests or contracts to pass; distinguish environment/operator
failures from defects and explain retries.
Review the final diff, status, and new files for scope, stale text, secrets,
generated artifacts, line endings, and compatibility. Check that no unintended
process, temporary file, server, or external operation remains.
If a required check cannot run or fails, report the missing evidence and risk;
never imply completion from test counts or partial checks alone.

## Git, filesystem, and privacy safety

Never overwrite, revert, stage, or incorporate unrelated user changes.
Destructive reset/checkout/clean/history rewrite/force-push require explicit
authorization for the exact operation and target.
Prefer reversible patches. Resolve and inspect exact paths before deletion,
overwrite, recursive move, or bulk rename; keep destructive targets within the
intended directory, never a root/home/workspace root, broad glob, or unresolved
variable. On Windows use literal paths in one shell for discovery and mutation.
Do not evade blocked destructive operations; report material removal/recovery.
Respect ignore rules. Keep credentials, private identity/background, local
session material, raw logs, models, caches, and large generated artifacts out
of tracked documentation. Treat input and command construction as untrusted;
do not expose secrets or weaken authentication, TLS, or validation.

## Kilo orchestration

Use advisory read-only reconnaissance/review when useful and permitted.
Before the first invocation, read [KILO_ORCHESTRATION.md](docs/reference/KILO_ORCHESTRATION.md)
and verify local configuration as described there. The runbook owns setup,
models, permissions, and invocation details.
The primary agent owns scope, implementation, tests, and findings. Kilo cannot
expand TASK.md, edit files, bypass gates, commit/push, or substitute for direct
inspection. Keep credentials outside tracked files.

## Documentation ownership and lifecycle

One fact, one owner: procedure here; current truth in STATE.md; authority in
TASK.md; architecture in ARCH.md; scientific design in RESEARCH.md; ordering in
ROADMAP.md; rationale in ADRs; exact results in evidence; superseded scope in
history; stable setup in reference. Link instead of mirroring.
Synchronize changed public behavior/interfaces/setup with their owners and
navigation. Distinguish planned, implemented, verified, committed, pushed,
experimentally validated, effectiveness demonstrated, and historical facts.

- TASK.md: keep only the current objective, scope, constraints, acceptance,
  verification, and stop conditions. On completion retire detailed scope to
  history only if useful and not already preserved; immediately return to a
  concise no-active-task body or the next explicitly authorized task.
- STATE.md: summarize the current frontier; collapse completed milestones into
  capabilities and evidence/history links instead of appending narratives.
- AGENTS.md: add procedure only for a concrete recurring repository failure;
  revise/merge existing rules before appending general engineering advice.
- ARCH.md: current/planned ownership and interfaces, not milestone chronology.
- RESEARCH.md: scientific design, not implementation status or results.
- ROADMAP.md: ordering/status at milestone granularity, not authorization.
- Evidence/history may grow under selective retrieval; never copy them back
  into hot context. Keep local routers and compatibility indexes small.

## Handoff

Give concise progress updates and report material failures promptly.
Final handoff: outcome, changed/new files, checks and supporting evidence,
limitations/unresolved risks, artifacts, and work intentionally left undone.
Report pre-existing changes separately and claim only actions actually verified.
