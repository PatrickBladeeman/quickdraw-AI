# ADR-0012: Store replay losslessly under a hard memory ceiling

- **Status:** Accepted and implemented in R3N
- **Recorded:** 2026-08-29, retrospectively

## Context

Separate full float32 `s` and `s'` arrays for 100,000 transitions of
`[84,84,4]` observations require `22,579,200,000` bytes (`21.03 GiB`) before
Python overhead. That is impractical on the registered 32 GB development
machine, while lossy compression would change replay semantics and invalidate
the frozen trace.

## Decision

Intern exact C-contiguous float32 channel frames by content and store eight
frame IDs plus actions, rewards, masks, and terminal fields in preallocated
columnar arrays. Reference counts reclaim orphaned frames after ring overwrite.
Sampling reconstructs the unchanged C-contiguous HWC float32 public batch.

Apply a deterministic `4 GiB` accounted-storage ceiling. Insertion is
transactional: if an arbitrary lossless stream would exceed the ceiling, raise
`MemoryError` and leave replay unchanged. Registered Basic projects to
`12,037,184` accounted bytes; the conservative 100,004-distinct-frame stream
projects to `2,934,585,088` bytes.

## Consequences

- Public replay fields, ring indices, sample draws, and optimizer math remain
  unchanged.
- The budget excludes caller-owned transitions, sampled batches, networks, and
  optimizer state and must not be presented as whole-process memory.
- R3N is lossless regression evidence, not a throughput benchmark.

See [`Research/trainer/bdq-replay-storage-contract-v1.json`](../../Research/trainer/bdq-replay-storage-contract-v1.json)
and [`Research/trainer/README.md`](../../Research/trainer/README.md).
