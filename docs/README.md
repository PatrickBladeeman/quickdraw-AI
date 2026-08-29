# Documentation map

This directory is the selective-loading index for durable project knowledge.
It does not replace the root authority documents and does not authorize work.

## Canonical root documents

| Document | Owns |
| --- | --- |
| [`AGENTS.md`](../AGENTS.md) | Repository procedure, safety, authorization, and quality gates |
| `CONTEXT.md` | Local ignored bootstrap and private-session routing |
| [`STATE.md`](../STATE.md) | Current verified repository and implementation state |
| [`TASK.md`](../TASK.md) | The current authorized task only |
| [`ARCH.md`](../ARCH.md) | Current architecture, component boundaries, and dependency direction |
| [`RESEARCH.md`](../RESEARCH.md) | Registered scientific design, hypotheses, thresholds, and training/evaluation contract |
| [`ROADMAP.md`](../ROADMAP.md) | Major milestone ordering and compact status |
| [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) | Compatibility index for older links |
| [`TASKS.md`](../TASKS.md) | Compatibility index for older task-ledger links |

Load only the documents needed for the current request. Historical material
never overrides current state, architecture, the registered research contract,
or repository procedure.

## Supporting memory

- [Decision records](decisions/README.md) explain why consequential choices were made.
- [Evidence](evidence/README.md) preserves milestone-specific claims, exact results, hashes, and negative evidence.
- [History](history/README.md) preserves superseded scopes and provenance without granting them current authority.
- [Reference](reference/README.md) contains stable setup, tuning, and artifact-handling information.

## Privacy boundary

Tracked documentation contains public project information only. Private
background, identity, authentication, machine-session, and local workflow
material stays in explicitly ignored local files. An omission made for privacy
is not documentation drift.
