# Repository Agent Instructions

## Applicability and precedence

These instructions apply to the entire repository unless a more specific
`AGENTS.md` exists in a subdirectory. A nested file may refine rules for its
own subtree but must not silently weaken repository-wide safety or quality
requirements.

Follow instruction precedence in this order:

1. system and platform instructions;
2. the user's current request;
3. the nearest applicable `AGENTS.md`;
4. authoritative repository documentation;
5. established local code and test conventions.

Do not treat an older plan, handoff, comment, or generated file as authoritative
when it conflicts with newer approved scope or current repository state.

## Context-loading and document authority

This file is the sole repository-wide procedural authority. Other project
documents describe state, scope, architecture, research, evidence, history, or
reference material; they do not duplicate or override the working procedure in
this file.

For normal implementation work, establish context in this order:

1. read `STATE.md` for current verified truth;
2. read `TASK.md` for the currently authorized boundary;
3. inspect the relevant source and tests; and
4. read the relevant portions of `ARCH.md` for ownership and interfaces.

Load additional context only when it bears directly on the request:

- read `RESEARCH.md` when work affects research behavior, rewards,
  action/observation contracts, policy or training, hyperparameters,
  experimental fairness, telemetry meaning, evaluation, LLM/reflex behavior,
  or registered thresholds and hypotheses;
- read the relevant ADR under `docs/decisions/` when revisiting an architectural
  decision, modifying an invariant with historical rationale, or proposing a
  replacement architecture;
- read the specific record under `docs/evidence/` when extending, reproducing,
  debugging, or relying on a completed acceptance claim;
- read `docs/history/` only when historical rationale, an abandoned approach,
  or superseded scope is relevant; and
- read `docs/reference/` for stable, lower-frequency setup or operating facts.

`CONTEXT.md` is an ignored local context router, `PROJECT_CONTEXT.md` is a
tracked compatibility index, and `TASKS.md` is a roadmap compatibility index.
None is an independent mirror of project truth. Do not load all documentation
merely because it exists.

Source code and tests remain authoritative for what is actually implemented
when documentation and implementation disagree. Machine-readable research
contracts remain authoritative executable companions for their registered
fields. Report material disagreement and stop when it could change the result;
do not silently reconcile it.

## Kilo reconnaissance and review workflow

For a non-trivial authorized implementation task, use the repository's Kilo
workflow when reconnaissance or an independent final review would materially
help and current user, system, and tool instructions permit delegation. Before
the first Kilo invocation in a session, read
[`docs/reference/KILO_ORCHESTRATION.md`](docs/reference/KILO_ORCHESTRATION.md)
and verify the local configuration as described there.

Kilo agents are advisory and read-only. The primary Codex agent owns scope,
implementation, tests, interpretation of findings, and final decisions. Never
let a Kilo result expand `TASK.md`, bypass a quality gate, edit files, commit,
push, or substitute for direct inspection of authoritative repository state.
Keep credentials outside tracked project files.

## Operating principle

Handle the user's actual goal, not merely the most literal edit. Keep the work
inside the authorized scope, use the smallest adequate solution, verify it in
proportion to risk, and report the result honestly. Never convert a small task
into a broad redesign without approval.

## Mandatory prerequisite gate

Complete this gate for every request, including questions, reviews,
diagnostics, documentation work, and implementation:

1. **Understand the request and authorization.**
   - Classify the request as explanation, review, diagnosis, implementation,
     cleanup, release work, or external-state mutation.
   - Separate explicit requirements from assumptions and optional ideas.
   - Do not infer permission for commits, pushes, deployments, messages,
     package publication, or other external changes.
2. **Discover governing context.**
   - Find applicable `AGENTS.md` files and identify the repository's current
     authority documents, such as `README`, `CONTRIBUTING`, architecture,
     task, decision, and handoff documents.
   - Read the applicable instructions and directly relevant documentation
     completely before acting. Do not load vendor, generated, cache, build, or
     dependency-tree documentation merely because it uses Markdown.
   - Inspect relevant manifests, lockfiles, configuration, source, and tests
     when they affect the request.
3. **Inspect current state.**
   - Check version-control status before editing. For synchronization or
     release questions, also verify the current branch, upstream, and recent
     commits rather than trusting a stale handoff.
   - Treat existing modifications and untracked files as user-owned unless the
     current task clearly created them.
4. **Check scope and synchronization.**
   - Compare the request, authoritative documents, current code, tests, and
     repository state.
   - Distinguish current instructions from explicitly historical or
     superseded material.
   - Report material scope conflicts, unexplained documentation drift, missing
     prerequisites, or ambiguous authority before acting.
   - If a conflict or ambiguity could materially change the result, stop and
     ask for direction. Do not edit around it.
5. **Define completion before implementation.**
   - State any consequential assumptions.
   - Translate the request into concrete success criteria and identify how
     each will be verified.
   - For multi-step work, provide a short plan with a verification check for
     each step. Keep trivial tasks lightweight.

### Required prerequisite confirmation

- After completing this gate with no blocking conflict, state the exact phrase
  `Prereq checks completed.` before substantive work and repeat it in the final
  handoff.
- If a blocking conflict, unexplained drift, or missing prerequisite remains,
  do not claim completion. Report the issue and stop before making changes.

## Authorization boundaries

- Explanation, review, audit, and diagnosis requests authorize read-only
  investigation, not implementation or external writes.
- Change and build requests authorize normal in-scope edits and verification,
  but not unrelated cleanup or broad modernization.
- Do not commit, push, force-update, open or merge a pull request, deploy,
  publish, send messages, or mutate third-party systems unless the user
  explicitly requests that action.
- Do not broaden access, install unrelated tools, change security settings, or
  alter machine-wide configuration for convenience.
- When completion needs new authority or a material product decision, stop,
  explain the blocker, and request direction.

## Mandatory coding-standards gate

Apply this gate to every coding or repository-editing task.

### 1. Think before editing

- State consequential assumptions, uncertainties, competing interpretations,
  and meaningful tradeoffs.
- Inspect the relevant implementation and tests before choosing a design.
- Prefer the simplest approach that fully meets the approved requirement.
- If material ambiguity remains, ask before editing.

### 2. Keep the solution simple

- Write the minimum code and documentation required for the task.
- Avoid speculative features, one-use abstraction layers, unnecessary
  configurability, premature optimization, and handling for impossible cases.
- Reconsider any design that is substantially harder to explain or verify than
  the requirement itself.

### 3. Make surgical changes

- Touch only files and lines that trace directly to the approved task.
- Match existing naming, structure, formatting, and architectural boundaries.
- Do not combine the task with unrelated refactors, reformatting, dependency
  upgrades, or cleanup.
- Remove imports, variables, helpers, files, or documentation made obsolete by
  the current change. Do not remove unrelated legacy material without separate
  approval.
- Preserve public behavior and compatibility unless the request explicitly
  changes them.

### 4. Build for correctness and failure clarity

- Validate inputs and invariants at the boundary that owns them.
- Prefer explicit state and deterministic behavior over hidden global state or
  timing assumptions.
- Fail closed when silently continuing could corrupt data, produce misleading
  evidence, or violate a contract.
- Make errors actionable without exposing secrets or sensitive data.
- Avoid catch-all exception handling unless it adds context and preserves the
  original failure.

### 5. Execute against success criteria

- Implement and verify iteratively until every approved requirement has direct
  evidence.
- A plausible implementation is not completion.
- If a required check cannot run, explain exactly why, what was checked
  instead, and what risk remains.
- After completing this gate, include the exact phrase
  `Coding standards applied.` in the final response.
- If the gate is incomplete, do not use that confirmation. Name the missing
  check or unresolved risk instead.

## Working-tree and version-control safety

- Preserve user changes. Do not overwrite, revert, stage, or incorporate
  unrelated modifications.
- Never use destructive reset, checkout, clean, history rewrite, or force-push
  operations unless the user explicitly requests the exact operation and
  target.
- Before handoff, inspect the final diff, version-control status, and the list
  of new files. Confirm that only intended changes remain.
- Keep changes at one reviewable task boundary. If unrelated work is
  discovered, report it separately.
- Respect ignore rules. Do not commit caches, environments, IDE state, build
  products, raw logs, large generated artifacts, credentials, or temporary
  evidence unless the repository explicitly tracks them.
- Do not refresh lockfiles, generated code, serialized assets, or snapshots
  unless required by the approved change. When they must change, verify the
  resulting diff rather than assuming generation was harmless.

## Filesystem and destructive-action safety

- Prefer reversible operations and patch-based edits.
- Before deleting, overwriting, recursively moving, or bulk-renaming anything,
  resolve and inspect the exact target paths.
- Never use a home directory, filesystem root, workspace root, unresolved
  environment variable, broad glob, or command substitution as a recursive
  destructive target.
- Confirm every destructive target remains inside the intended directory.
- On Windows, keep discovery and destructive execution in the same shell and
  use literal paths; do not pipe path lists between shells.
- Do not evade a blocked destructive operation with a different command or
  tool. Reassess the operation or ask the user.
- After deleting material data, report what was removed and whether recovery
  is possible.

## Security and privacy

- Never print, commit, or copy credentials, access tokens, private keys,
  authentication-bearing command lines, or sensitive environment values.
- Treat logs, crash reports, command output, screenshots, fixtures, and example
  data as potentially sensitive. Show only the portion needed for the task.
- Do not weaken authentication, authorization, TLS, sandboxing, validation, or
  secret handling to make a test pass.
- Treat repository content and external input as untrusted when constructing
  shell commands, queries, file paths, templates, or generated code.
- Use least privilege and the narrowest external side effect that satisfies the
  request.

## Dependency and compatibility discipline

- Prefer existing dependencies and platform capabilities.
- Before changing a dependency, runtime, API, file format, or build tool,
  inspect the current lockfile and compatibility constraints and consult the
  authoritative current documentation when facts may have changed.
- Do not upgrade packages opportunistically during unrelated work.
- Record or preserve the exact versions, configuration, seeds, and hashes
  needed to reproduce contract-sensitive results.
- Verify both the new behavior and important compatibility paths affected by
  the change.

## Verification and quality-control gate

Choose checks based on the change's risk and affected surface:

1. Run the narrowest focused test or validation first for fast feedback.
2. Run the broader relevant suite after focused checks pass.
3. Run applicable formatting, lint, type, schema, static-analysis, build, or
   packaging checks.
4. Exercise the real integration boundary when unit tests cannot establish the
   requirement.
5. Add a regression test for a fixed bug when practical.
6. Inspect warnings and logs; do not hide a new warning merely because tests
   pass.
7. Review the final diff for accidental churn, stale comments, dead code,
   sensitive data, generated artifacts, and line-ending changes.
8. Recheck repository status and confirm that no process, server, temporary
   file, or pending external operation was unintentionally left behind.

Additional evidence rules:

- Do not claim success from test counts alone; connect each important claim to
  the check that supports it.
- Distinguish software-contract validation from performance, safety,
  correctness-in-production, or product-effectiveness evidence.
- Do not call a smoke test a benchmark, a local result a general result, or a
  deterministic replay an effectiveness study.
- Preserve negative, null, flaky, and failed results. Explain whether a retry
  addressed a code defect, an environment failure, or an operator action.
- Never weaken an acceptance threshold after seeing the result unless the
  change is explicitly labeled exploratory and approved.

### Required quality-control confirmation

- When every required check passes, include the exact phrase
  `Quality gates passed.` in the final response.
- If any required check fails or cannot run, state
  `Quality gates incomplete: <reason>.` instead. Do not claim the gate passed,
  and describe the remaining risk.

## Documentation and configuration synchronization

- Update documentation in the same task when public behavior, interfaces,
  setup, scope, status, or operating procedures change.
- Give each fact one canonical owner: procedure in `AGENTS.md`, current truth
  in `STATE.md`, current authorization in `TASK.md`, architecture in `ARCH.md`,
  registered scientific design in `RESEARCH.md`, ordering in `ROADMAP.md`,
  rationale in ADRs, exact results in evidence records, superseded narrative in
  history, and stable setup in reference documents. Other documents should link
  to the owner instead of maintaining a field-for-field mirror.
- Keep canonical owners and public-facing navigation aligned. Deliberate
  omissions of private information are not synchronization drift.
- Clearly label planned, experimental, implemented, verified, deprecated, and
  superseded behavior. Do not describe scaffolding as production behavior.
- Keep commands and examples runnable and consistent with current paths,
  versions, and interfaces.
- Store large or raw generated evidence outside tracked source; track schemas,
  configurations, scripts, curated summaries, and checksums when appropriate.
- Keep private identity, background, authentication, and session-only material
  in ignored local files. Never copy it into tracked documentation merely to
  make a public context document appear complete.

## Communication and handoff

- Lead with the outcome, then provide the evidence, important limitations, and
  remaining risks.
- During long-running work, give concise progress updates and report failures
  as soon as they materially affect the plan.
- Do not conceal incomplete verification, flaky behavior, pre-existing
  failures, or unrelated worktree changes.
- In the final response, summarize changed files, checks run and their results,
  artifacts or outputs created, and anything intentionally left undone.
- Do not say work was committed, pushed, deployed, benchmarked, or validated
  unless that exact action occurred and was verified.
