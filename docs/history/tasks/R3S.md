# R3S — Live Unity trajectory resumption and learned-policy export parity

> Historical, completed specification retired from TASK.md on 2026-09-10.
> It grants no current authority; see [TASK.md](../../../TASK.md).
> Exact accepted results and rejected attempts belong in [R3S evidence](../../evidence/R3S.md).

The user explicitly authorized this next bounded research-infrastructure task
on 2026-09-08. Extend the accepted R3R synchronization boundary in two ordered
packages:

1. prove a real live Unity trajectory handoff across a trainer checkpoint save
   and fresh trainer-process restore; and
2. export the exact accepted R3R learned network to ONNX and prove
   exported-inference parity with the Python BDQ reference.

R3S is a reproducibility and serving-boundary task. It is not unrestricted
training, a convergence run, policy-effectiveness evidence, held-out
evaluation, or final checkpoint selection.

## Starting boundary

The accepted R3R input identities, counters, runtime, seeds, and network hashes
are retained in [R3S evidence](../../evidence/R3S.md) and its linked contract.
Missing or mismatched starting artifacts required rejection, not recreation
of a different state.

## Implementation boundary

### 1. Contract, schemas, and bounded entry point

- Add one versioned R3S contract at
  `Research/trainer/bdq-live-resume-export-contract-v1.json`.
- Add a contract schema at
  `Research/schemas/bdq-live-resume-export-contract.schema.json` and a result
  schema at `Research/schemas/bdq-live-resume-export-result.schema.json`.
- Add the bounded compatibility entry point
  `Research/trainer/run_bdq_live_resume_export_smoke.py` and focused tests at
  `Research/trainer/test_bdq_live_resume_export.py`.
- Add the acceptance record `docs/evidence/R3S.md`. Keep raw runs, player
  copies, logs, checkpoints, handoff metadata, exported models, input
  corpora, comparison results, and rejected attempts under the ignored
  directory `Artifacts/Experiments/r3s-live-resume-export/`.
- Bind the new contract to the R3R contract, accepted result, canonical trace,
  trainer checkpoint, checkpoint state, online-network hash, target-network
  hash, runtime identity, package identity, player manifest, and export
  metadata. Validate hash-bound artifacts before relational checks.
- Use the existing capability owners in `quickdraw_bdq`:
  `checkpoint.py` for trainer state, `llapi.py` for decision and transition
  transport, `acceptance.py` and `provenance.py` for process/player identity
  and hashing, and `update_gate.py` only for bounded collection behavior.
  Do not create a generic resume framework or duplicate existing checkpoint,
  process-launch, or schema-validation mechanisms.
- Record canonical deterministic fields separately from volatile fields such
  as process IDs, wall-clock times, temporary paths, and log locations.
  Volatile metadata may be retained for provenance but must not make an
  otherwise identical canonical continuation differ.
- Preserve generic schema validation before relational validation and preserve
  actionable failure types, messages, and ordering where observable.

### 2. Live Unity trajectory handoff

A valid live-resume proof must preserve one live Unity player process across
the trainer handoff. Deterministic replay into a fresh player copy is allowed
only to establish the accepted starting boundary; it is not evidence of
resumption.

- Each attempt may start from a fresh, run-owned, complete copy of the
  accepted player. The copy must include the executable, its `*_Data`
  directory, Unity player libraries, and required sibling files. Never launch
  a frozen historical directory directly.
- Run the unchanged player to the R3R boundary and verify the transition,
  decision, replay, network, target, selector, optimizer, RNG, and checkpoint
  state against the accepted R3R artifacts before selecting the next action.
- Reach a clean handoff point with no pending trainer action, save the
  versioned trainer checkpoint, and write a handoff manifest without
  selecting the next live action.
- Keep the same Unity player process, player state, and communication session
  alive across the handoff. A fresh Python trainer process must restore the
  checkpoint and take over the live connection through an explicit local
  handoff mechanism. A supervisor or proxy is allowed only when it makes the
  connection ownership and state transfer observable and deterministic.
- Prove process continuity using a process identity that cannot be confused
  with a relaunch, such as the PID plus a platform-safe creation/start marker
  and the run-owned player manifest. Record the launch command, executable
  identity, player-copy manifest, and handoff events.
- Prove that the handoff did not call Unity reset, relaunch the executable,
  replace the player copy, consume an extra environment step, duplicate a
  transition, discard a decision, or change the behavior/agent identity.
  The restored trainer must begin from the pre-existing live decision state.
- Restore into a fresh trainer process and verify the R3R state before
  selecting exactly one legal post-resume live action at completed-transition
  count `49,996`. Step the same Unity process exactly far enough to complete
  that action as transition `49,997`.
- Stop at the next clean trainer boundary immediately after transition
  `49,997` and before selecting another action. The live handoff package must
  end with exactly one post-resume live action, `49,997` completed
  transitions/decisions, optimizer update `10,000`, target synchronization
  count `1`, no pending trainer agent IDs, and no discarded action.
- The one-transition continuation must not execute optimizer update `10,001`.
  With the registered update interval, the next update would occur at
  transition `50,000`; that update and all later work are outside this task.
- Run at least two independent fresh attempts. Each attempt must demonstrate
  same-process Unity continuity within the attempt, and the canonical
  post-handoff observation, action, masks, reward, episode/truncation fields,
  trainer state, and hashes must match across attempts. Preserve process and
  timing differences only as noncanonical provenance.
- If the transport cannot support a fresh trainer handoff to the same live
  Unity process, stop with an explicit rejected result. Do not substitute
  prefix replay or a fresh player restart and call it live resume.

### 3. Learned-policy ONNX export and inference parity

Export only the accepted R3R post-synchronization online network. The export
package must not perform another optimizer update, change the checkpoint, or
select a policy action for evaluation.

- Export from the online network whose accepted R3R SHA-256 is
  `5e455aac0264f98a364ec9d296671e91539fea0522d48f438b416950983f747f`.
  Confirm that the state-dict/network hash is unchanged before and after
  export. Record the ONNX file SHA-256, exporter version, ONNX opset, graph
  input/output names, and inference-runtime version.
- Keep the registered Python training dependency set and CPU reference
  unchanged. If an ONNX exporter or inference runtime is needed, isolate it
  as a version-pinned export/parity dependency, record its exact version and
  platform in the R3S contract, and verify compatibility before acceptance.
- Define and enforce the exported graph interface:
  - input `observations` is nonempty float32 HWC data with shape
    `[N,84,84,4]` and values in `[0,1]`;
  - output branch 0 is float32 Q-values with shape `[N,3]`;
  - output branch 1 is float32 Q-values with shape `[N,2]`; and
  - branch order, output order, normalization, and batch behavior are
    explicit. Test both `N=1` and a batched input.
- Do not put privileged scene state or inferred legality into the exported
  graph. Apply the same authoritative action masks and deterministic
  branch-wise masked-argmax/tie-breaking used by the Python selector to both
  Python and exported Q-values.
- Create a versioned, hash-bound parity corpus of at least `64` observations
  from the accepted R3R trace/checkpoint and the live-resume boundary. Include
  every branch mask pattern present in the corpus, legal and unavailable
  actions, and the one post-resume observation. Record the corpus-selection
  rule, input bytes/hash, masks, and expected Python outputs/actions.
- Compare Python and ONNX branch Q-values on the exact corpus with the
  pre-registered acceptance tolerance
  `maximum absolute difference <= 1e-5` for every finite output element.
  Do not choose or relax the tolerance after seeing the result.
- Require exact equality of the final masked legal action tuple for every
  corpus item, including deterministic tie cases. Reject output shape, dtype,
  range, finiteness, branch-order, mask, or action mismatches.
- Repeat ONNX inference in at least two independent fresh CPU processes and
  require identical canonical outputs and actions. Record noncanonical timing
  separately; this is an inference-parity check, not a performance benchmark.

### 4. Validator, negative cases, and compatibility

- The R3S validator must reject:
  - a missing, stale, or hash-mismatched R3R contract, result, trace,
    checkpoint, network, player manifest, or export;
  - a starting transition/update/synchronization counter drift;
  - a pending trainer action or pending agent at the R3R handoff;
  - a Unity PID/start-marker change, reset, relaunch, replacement player
    copy, behavior change, extra environment step, duplicated transition,
    discarded decision, or action selected before restore;
  - a final count other than exactly one resumed action and transition
    `49,997`;
  - optimizer update `10,001`, target synchronization count other than `1`,
    or any second synchronization;
  - checkpoint integrity, package, runtime, settings, seed, selector, RNG,
    replay, network, target, or boundary-state drift;
  - missing or noncanonical process-handoff evidence; and
  - malformed export metadata, wrong graph input/output shape or order,
    wrong dtype, nonfinite values, tolerance excess, mask/action mismatch,
    nondeterministic repeat output, or a stale network hash.
- Existing R3O, R3Q, and R3R validators, schemas, evidence, accepted traces,
  results, checkpoints, and frozen contract files must remain byte-identical.
  Their existing failure behavior and focused regression tests must continue
  to pass.
- Add a regression test for every new rejection class that is practical to
  exercise without Unity. Keep live-process tests on the pinned integration
  path and fail closed when the required player or transport is unavailable.

## Invariants

Preserve the network architecture, observation bytes and HWC layout, branch
action semantics, authoritative legality masks, reward and episode boundaries,
replay representation and accounting, optimizer algorithm and counters,
target-synchronization history, checkpoint encoding, selector and RNG
ownership/consumption, deterministic CPU settings, runtime versions, and all
registered seeds and values. Do not change the Unity scene, gameplay
mechanics, player settings, environment contract, or accepted R3O/R3Q/R3R
artifacts to make the handoff or export pass.

The ONNX model is an artifact-level export of the accepted R3R online network.
Parity does not establish policy quality, generalization, sample efficiency,
training effectiveness, or production readiness.

## Acceptance criteria

- The R3S contract and both schemas are explicit, versioned, hash-bound, and
  validated before relational checks. The contract freezes the live-handoff
  protocol, exact start/final boundaries, process-continuity evidence,
  export interface, parity corpus, tolerance, runtime versions, and
  canonical/volatile field rules.
- The R3R starting boundary is reproduced exactly before the new live action:
  `49,996` transitions/decisions, update `10,000`, sync count `1`, target and
  online hashes bound to the accepted R3R result, no pending trainer action,
  and no post-boundary action selected.
- At least two fresh live attempts preserve the same Unity process across the
  trainer checkpoint save and fresh Python-process restore. No reset, relaunch,
  player replacement, extra step, duplicate transition, or discarded action
  occurs.
- Each live attempt selects exactly one legal post-resume action at count
  `49,996`, completes exactly transition `49,997`, retains update count
  `10,000` and sync count `1`, and stops before the next action. No update
  `10,001` or second synchronization occurs.
- The canonical post-resume transition, trainer/checkpoint state, replay/RNG
  state, hashes, and boundary summary match across independent attempts. The
  evidence makes clear which process/timing fields are provenance only.
- The exported ONNX file is bound to the accepted R3R online-network hash,
  has the registered interface and recorded exporter/runtime metadata, and
  supports the required single-item and batched inputs.
- Every corpus Q-value is finite and within maximum absolute error `1e-5`
  against Python, every masked legal action tuple matches exactly, and two
  fresh CPU inference processes reproduce the same canonical outputs/actions.
- New negative tests cover live handoff drift, boundary/action drift,
  update/synchronization overflow, checkpoint/RNG/network mismatch, export
  metadata/interface/output/tolerance drift, mask/action mismatch, and
  nondeterministic inference. Existing focused and complete trainer suites
  remain passing.
- The pinned Unity/LLAPI integration path, schema/result validation,
  frozen-artifact hash audit, process-leak check, and configured read-only
  contract review pass. Any environment failure is retained as a rejected
  result rather than hidden or retried into acceptance.
- Ignored artifacts retain the exact commands, package/runtime versions,
  seeds, contract/schema/export/corpus hashes, player manifest, process
  handoff log, raw traces, checkpoints, ONNX file, Python/ONNX comparisons,
  summaries, and all failed or rejected attempts. No profiling or handoff
  output is written into a frozen player directory.
- The final evidence and report distinguish live-process continuity and
  exported-inference software parity from deterministic replay and from
  training-effectiveness evidence. The report does not claim convergence,
  held-out success, five-seed completion, policy improvement, final checkpoint
  selection, ROCm training, strategic combat, or a useful policy.

## Explicit exclusions and stop rules

- Do not run optimizer update `10,001`, a second target synchronization, any
  extended post-resume rollout, the five-seed training campaign, held-out
  evaluation, the joint-action Double-DQN comparison, or final checkpoint
  selection.
- Do not change the registered update interval, synchronization interval,
  learning rate, gamma, replay capacity, warmup, batch size, epsilon schedule,
  action space, rewards, masks, episode/truncation semantics, or seeds.
- Do not call deterministic prefix replay into a fresh player, a fresh Unity
  launch, a reset environment, or a Python-only checkpoint restore a live
  Unity-process resume. Those mechanisms may establish or validate the
  starting boundary only.
- Do not claim that the archived/frozen historical R3R Unity process was
  resumed unless the evidence directly proves that exact process identity.
  The minimum R3S claim is continuity of one run-owned live player across the
  trainer handoff.
- Do not export a different, newly trained, partially updated, or
  post-resume-weight network. Do not use ONNX or parity output as
  effectiveness evidence.
- Do not execute ROCm training or inference for this task, alter the
  Research_Basic scene or player settings, implement the gradual-motion
  variant, strategic combat, the research reflex, an LLM/director runtime, or
  an unrestricted training/resume framework.
- Do not overwrite accepted evidence, regenerate frozen artifacts, weaken
  validation, lower the registered parity tolerance, or silently omit failed
  attempts.
- Do not commit, push, open a PR, deploy, publish, or mutate third-party
  systems without separate explicit authorization.
