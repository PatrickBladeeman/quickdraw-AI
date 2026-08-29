# Public project history through R3N

> **Historical and non-authoritative.** This is a sanitized chronology, not a
> statement of current authorization. Consult [`STATE.md`](../../STATE.md) and
> [`TASK.md`](../../TASK.md) before acting.

## From broad game idea to a measurable fixture

The project began as a broader exploration of layered FPS NPC behavior,
including urgent reactions, tactical reasoning, and eventual local-model
enrichment. It was deliberately reduced to a small behavior laboratory so that
perception, interruption, reaction timing, and telemetry could be made
observable before learned or generative systems were introduced.

The first accepted vertical slice became `Test_Arena`: a deterministic player,
patrol NPC, structured aim stimulus, soft perception, one-shot interruption,
collision-aware `Flinch_StepBack`, observed visible-motion onset, and buffered
typed JSONL telemetry. The abandoned automatic tactical-recovery FSM was never
implemented.

## Research pivot

Once Tasks 1–8 supplied a measured deterministic substrate, the project adopted
its current research question: whether mechanical control, urgent reflexes,
learned tactical action, and slow local-LLM strategy can be separated by
timescale without slow inference damaging urgent responsiveness.

The pivot preserved `Test_Arena` as a regression fixture and introduced isolated
research surfaces:

- `Research_Smoke` for Unity/Python transport;
- `Research_Basic` for deterministic visual Q-learning;
- a planned `Research_Strategic` factorial benchmark;
- a custom Branching Double DQN loop over the ML-Agents low-level API.

The registered scientific design is now maintained separately in
[`RESEARCH.md`](../../RESEARCH.md).

## Public milestone chronology

| Milestone | Public result | Commit |
| --- | --- | --- |
| Tasks 1–8 | Deterministic fixture and telemetry checkpoint | `ac1274e`, `b5532e1` |
| R1A | Dependency and contract preflight | `7117b81` |
| R1B | ML-Agents package and repeatable communicator smoke | `4863153` |
| R1C | Exact 10,000-decision CPU transport reference | `5bae5f1` |
| R1D | Exploratory accelerator lane; superseded and retired | no accepted implementation commit |
| R1E | Python 3.11.13 / ML-Agents 1.1.0 / ROCm 7.14 compatibility lane | `6d2aa3b` |
| R1F | Fixed-policy CPU/ROCm parity and registered inference-scope acceptance | `876cedd` |
| R2A | Deterministic `Research_Basic` visual environment | `3cf3494` |
| Gradual-motion note | Preserved slot Basic and deferred a separately versioned variant | `3427c14` |
| R3A | BDQ tensor, replay, network, target, and loss foundation | `20aeab7` |
| R3A synchronization | Follow-up public documentation alignment | `7df359e` |
| R3B | Deterministic optimizer and schedule smoke | `500bc24` |
| R3C | High-level trajectory experiment; superseded before acceptance | no accepted implementation commit |
| R3D | Direct LLAPI collection and truncation-mask transport | `a4b449d` |
| R3E | Fixed seeded epsilon-greedy collection below warmup | `6aef062` |
| R3F | 10,000-transition warmup, first real-Unity update, and watch mode | `7edf7a3` |
| R3G | Second scheduled optimizer update | `df036eb` |
| R3H | Twice-updated online weights drive one live masked-greedy action | `769c4de` |
| R3I | Stateless production epsilon schedule | `8d999d4` |
| R3J | Bounded live scheduled-epsilon integration | `32e78c6` |
| R3K | Third scheduled optimizer update | `2960e5b` |
| R3L | Update-3 live masked-greedy diagnostic handoff | `f586507` |
| R3M | Fourth scheduled optimizer update | `2ec3ec3` |
| R3N | Lossless, memory-bounded replay storage | `ca66335` |

R3N is the history cutoff for this record. It was committed and pushed on
`main` as `ca66335` before the documentation migration began.

## What this chronology does not prove

The first four bounded optimizer updates are integration evidence, not extended
training or policy-effectiveness evidence. At the R3N cutoff there was no fifth
update, target synchronization, extended epsilon-decay rollout, learned-policy
evaluation, strategic combat runtime, research evade reflex, or local-model
runtime. Historical completion labels must not be expanded beyond the evidence
recorded for each milestone.

See [`docs/evidence`](../evidence/README.md) for exact counts, hashes, losses,
negative evidence, and claim boundaries.
