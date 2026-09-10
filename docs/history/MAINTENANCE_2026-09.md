# Maintenance and repository checkpoint provenance

> Historical record extracted from STATE.md on 2026-09-10.
> These dated checkpoints do not describe current authorization or Git state.
> Current truth: [STATE.md](../../STATE.md).

## Documentation and tooling checkpoints

- Hierarchical documentation migration and QA: `563c726fb3e782bd3bece11c0ce38dbcf3a8feed`
  and `abd240f9551bfc077e38672f06e7071d5480bc44`, recorded committed/pushed.
- Read-only Kilo workflow: `75bfb6427a1f17518e0b8487d7cdf8c31399f7d8`,
  recorded committed/pushed. Operating guidance lives in
  [the reference runbook](../reference/KILO_ORCHESTRATION.md).
- R3P: `0d78c783897225395ed44304fb6b0124a4620582`, recorded committed/pushed.
- R3Q: `549617b08b0d88199c0a97531350d9c61a2428ae`.
- At R3S task start, `main` and local `origin/main` were recorded at R3R
  `885da143b01e6309e7b215afd684fd2977fd2f90`; R3S changes were then uncommitted.
  R3S subsequently became commit `61ba19ebe9fab3c888fc67c88cdeb30a6333e86c`.
  Exact research results remain in [evidence](../evidence/README.md).

## Acceptance-harness maintenance

A conservative consolidation of the Python research acceptance harness is
implemented, verified, committed, and pushed at
`4fa825b6c8ca45797abaaf6da85cde9357aa3657`.
Generic acceptance utilities and the shared update-gate implementation
live in capability-oriented `quickdraw_bdq` modules while all historical
runner paths remain compatibility entry points.

The complete trainer suite and representative historical artifacts pass, the
independent read-only contract review found no blocking drift, and all frozen
contracts, schemas, evidence, and original production-core files remain
byte-identical. This work does not advance the R3 research frontier, change any
registered research value or accepted result, or authorize new Unity
collection.

The second implementation consolidation is complete, verified, committed, and
pushed at `d4f935152c4731c8892b49ffac38d23d90895a7b`. It shares the eight
trajectory entry flows, repeated contract/prefix validation, scheduled-update test fixtures,
PlayMode reflection helpers, raw-file/runtime provenance, R3P process launch,
and Unity build/report handling. Historical commands and frozen research
formats remain intact; [`ARCH.md`](../../ARCH.md) owns the new module boundaries.
The three collection loops remain distinct because sharing their substantial
body would require new event-order tests and more control machinery.
The trajectory validators remain specialized to the registered historical
milestones; they are not an unrestricted training runner.

At that earlier maintenance checkpoint, the complete trainer suite passed 277 cases and the unchanged 41 PlayMode
cases pass. Both historical Unity build entry methods produced fresh players
from existing scenes. R3O traces/results and R3P/R3Q checkpoints/results match
the accepted raw bytes. All 21 explicit path/SHA contract
bindings pass. Of 273 task-start manifest entries, 272 match and one records
ML-Agents rewriting the historical player's unbound `Research_Basic_timers.json`
timing log. Its original hash and the failed strict audit are retained. On
2026-09-07 the user authorized completion without restoring that log; the
exception remains explicit in the complete manifest comparison. Two read-only
Kilo reviews covered the change; the first review's render-asset line-ending
finding was resolved, and the second found no substantive new issue.
Verification passes within the updated authorized scope.
The maintenance boundary is completed; current authorization belongs in
[`TASK.md`](../../TASK.md).
