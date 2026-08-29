# Documentation migration — 2026-08-29

> **Migration provenance, not current authority.** This record explains how
> knowledge was redistributed. Current ownership is defined by
> [`docs/README.md`](../README.md) and repository procedure.

## Starting point

The repository accumulated five large overlapping documents:

- local ignored `CONTEXT.md` mixed procedure, current state, research design,
  history, reference material, and private session context;
- tracked `PROJECT_CONTEXT.md` mirrored most public content;
- `ARCH.md` mixed architecture, research registration, status, and evidence;
- `TASKS.md` mixed completed evidence, current execution, future roadmap, and
  procedural rules;
- `AGENTS.md` already held strong general safety and quality gates but lacked a
  project document-loading map.

At the migration checkpoint, Git `main`, its upstream, and `origin/main` all
resolved to pushed R3N commit `ca66335` (`R3N: lossless replay storage
optimization`). Existing unstaged edits to `PROJECT_CONTEXT.md` and `TASKS.md`
recorded that synchronization and were treated as intentional in-scope state.

## New ownership

| Knowledge | Canonical destination |
| --- | --- |
| Procedure, authorization, safety, and quality gates | root `AGENTS.md` |
| Local bootstrap and private routing | ignored root `CONTEXT.md` |
| Current verified truth | root `STATE.md` |
| Current authorized task | root `TASK.md` |
| Current architecture and code boundaries | root `ARCH.md` |
| Registered scientific contract | root `RESEARCH.md` |
| Major ordering and compact status | root `ROADMAP.md` |
| Decision rationale | `docs/decisions/` |
| Exact milestone results and negative evidence | `docs/evidence/` |
| Superseded scopes and provenance | `docs/history/` |
| Stable setup and operating reference | `docs/reference/` |
| Legacy public entry points | small compatibility shims |

## Rules deliberately retired

- `CONTEXT.md` is no longer the sole project authority.
- Agents do not read every repository Markdown file for every request.
- `CONTEXT.md` and `PROJECT_CONTEXT.md` are not mirrored copies.
- Old local handoffs and archived prompts do not impose procedure.
- Historical milestone checklists do not authorize the next implementation.
- Obsolete confirmation phrases are replaced by the exact confirmations in
  current `AGENTS.md`.

Selective loading does not weaken the prerequisite, coding, safety, privacy, or
quality gates. It changes where knowledge lives and which relevant documents
must be read.

## Preservation and privacy

Public hypotheses, thresholds, hyperparameters, seed rules, version pins,
hashes, test counts, transition counts, losses, TD errors, commit provenance,
qualifications, and negative/null evidence are routed into registered research
or milestone evidence files. Historical alternatives remain explicitly labeled.

Private background, identity, authentication, and local-session information is
not copied into tracked documentation. Existing ignore rules matched local
memory filenames exactly, so local archival safety had to be established before
shrinking or renaming any ignored source.

## Completion criterion

This migration is complete only when all canonical files exist, legacy entry
points route rather than mirror, current Git state agrees with `STATE.md`, the
registered contract preserves exact values, links resolve, privacy boundaries
hold, and a final diff/status audit finds only intended documentation changes.
