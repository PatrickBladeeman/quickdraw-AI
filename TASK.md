# quickdraw-AI — Current Authorized Task

Last updated: 2026-09-10

## Objective

**R3T — Basic BDQ multi-seed training and lineage** is authorized on
2026-09-10; implementation has not started. Run the five registered Basic BDQ
training seeds and preserve complete, reviewable lineage. This is a bounded
training and artifact-integrity task, not held-out evaluation or convergence.

Current truth: [STATE.md](STATE.md). Ordering: [ROADMAP.md](ROADMAP.md).
Most recently completed: R3S live-process handoff and accepted-network export
parity; see [evidence](docs/evidence/R3S.md).

## Scope and required registration

Extend existing Basic collection, replay, checkpoint, optimizer, and acceptance
mechanisms through contract/configuration data. Before collecting any dependent
training data, register a decision record, synchronize [RESEARCH.md](RESEARCH.md),
and add a versioned R3T contract under `Research/trainer/` with matching
contract/result schemas under `Research/schemas/`. Freeze:

- exact training horizon in decisions/transitions and optimizer updates, with
  a clean stopping boundary;
- checkpoint cadence, contents, and deterministic selection using only
  predeclared training information;
- stopping/invalid-run criteria, preserving infrastructure failures,
  incomplete seeds, and rejected attempts;
- seed-to-run mapping, episode/scenario training coverage, and separation
  from later held-out evaluation seeds;
- learning-curve sampling interval, return/success definitions, and metric
  aggregation/denominators;
- runtime, player, source, configuration, and artifact identities/hashes; and
- artifact layout and result fields sufficient for reproduction without
  volatile paths or process IDs.

Do not choose values for convenient duration or favorable outcomes. Later
held-out seed registration, effectiveness thresholds, and joint-action
comparison remain separate work; never inspect their outcomes for selection.

## Constraints

- Each policy seed starts with fresh online/target initialization, empty replay,
  fresh optimizer and selector state, and a fresh complete run-owned copy of
  the accepted Basic player. No R3S continuation or cross-seed weight transfer.
- Preserve the Basic identity, scene, single agent, HWC observation, branches,
  masks, rewards, terminal/truncation semantics, network, replay accounting,
  Adam, update/epsilon/target-sync schedules, and CPU RNG ownership.
  Exact values belong in [Basic](RESEARCH.md#basic-visual-control-benchmark),
  [BDQ](RESEARCH.md#branching-double-dqn-contract), and
  [seed](RESEARCH.md#seed-contract) contracts and their machine-readable owners.
- Use all five registered policy seeds, the registered Basic scenario seed,
  and registered exploration mapping. Register any needed mapping extension
  before running; never derive seeds from names, hashes, process IDs, or clocks.
- Preserve the pinned deterministic CPU runtime, one Torch thread and one
  interop thread. Record package, platform, hardware, player, and source identity.
- Validate contract/player hashes and identity before launch. Isolate profiling
  output; never launch or write into frozen historical player directories.
- A thin bounded campaign entry point is allowed only if existing flows cannot
  express the five-run configuration; reject unknown seeds, horizons, settings.
  No generic/unbounded trainer or duplicate production BDQ path.

## Acceptance criteria

- Decision record, research registration, contract, and schemas agree and
  validate before dependent runs. Bind unchanged Basic/BDQ contracts, runtime/
  source, seed mapping, horizon, checkpoint rule, and artifact layout.
- All five seeds reach their exact registered clean transition/decision/update
  boundaries under the same environment/algorithm contract, without duplicate,
  discarded, partial, unaccounted transitions/updates or post-boundary actions.
- Preserve complete ordered transition and episode data: action/mask fields,
  rewards, terminal/truncation flags, decision/update counters, epsilon, replay
  size/accounting, target synchronizations, and rejected/invalid events.
- Record every registered learning-curve update: Huber loss, mean absolute TD
  error, online/target hashes, replay and RNG/checkpoint-equivalent state,
  Q-value summaries, timings, return/success, provenance, and configuration.
  Registered metrics must be finite with explicit denominators.
- Save checkpoints at registered cadence/selection boundaries, including online/
  target networks, optimizer, replay, selector/RNG, counters, settings, seed
  mapping, and all existing validator fields. Each seed's selected checkpoint
  must match state-dict, optimizer, replay, RNG, counters, settings, and hashes
  in a fresh Python process. This does not prove Unity-process resumption.
- All five result records/checkpoints validate and are reproducible from recorded
  commands and identities. Volatile IDs, timestamps, and paths cannot affect
  canonical equality. Store raw traces, checkpoints, manifests, metrics, rejected
  attempts, and summaries only in ignored
  `Artifacts/Experiments/r3t-basic-multiseed/`; track only contracts, schemas,
  commands, curated summaries, and checksums.

## Verification

- Apply generic schema validation before relational checks for seed, counters,
  hashes, cadence, sync history, replay, finite metrics, and canonical fields.
- Existing R3O/R3Q/R3R/R3S artifacts, contracts, validators, schemas, evidence,
  traces, results, and checkpoints remain byte-identical. Run their focused
  validators/regressions and the complete trainer checks.
- Add negative cases for seed, horizon, settings, hash, counters, replay,
  checkpoint, provenance, metrics, and artifact-layout drift.
- Pass configured read-only contract review, process-leak, player-provenance,
  frozen-artifact, schema, hash, and result audits. Retain failures as rejected
  results; acceptance requires all five seeds to satisfy the contract.
- Report finite training completion and lineage without claiming success-rate
  improvement, policy effectiveness, convergence, generalization, sample
  efficiency, final policy choice, hypotheses, or ViZDoom numeric replication.

## Exclusions and stop conditions

No held-out learned-policy evaluation, application of Basic effectiveness
thresholds, six-joint-action Double-DQN control, multi-environment collector,
gradual-motion variant, strategic scene, research reflex, LLM director,
factorial runner, or new ONNX/live-handoff boundary. No unregistered
duration/stopping/selection choices during execution. Checkpoint parity,
deterministic replay, training telemetry, and R3S parity are not effectiveness
evidence.

Stop and retain a rejected result for contract disagreement, player/runtime
drift, seed mismatch, missing artifacts, replay/accounting overflow, process
leaks, nonfinite metrics, checkpoint mismatch, or unapproved settings.
Never weaken thresholds or overwrite accepted evidence after seeing results.
No commit, push, PR, deployment, publication, or third-party mutation is authorized.
