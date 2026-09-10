# quickdraw-AI — Current Authorized Task

Last updated: 2026-09-09

This file is the canonical answer to **what work is authorized right now**.
It records the current authorization and the completed-boundary context needed
to interpret it; speculative later work is excluded.

## Completed prior tasks

The second implementation consolidation is complete, verified, committed, and
pushed at
`d4f935152c4731c8892b49ffac38d23d90895a7b`. It reduced repeated trajectory
orchestration, contract/prefix validation, test fixtures, PlayMode reflection,
process/hash/runtime utilities, and Unity build plumbing. Its current truth and
limitations are recorded in [`STATE.md`](STATE.md).

## Completed prior task — R3R

### Long-horizon BDQ continuation and first target synchronization

The user approved this bounded research implementation on 2026-09-07. It is
complete and verified. It extended the unchanged slot-based
`Research_Basic` Branching Double DQN path
beyond the R3O/R3Q boundary in two ordered packages:

1. a substantial one-seed continuation pilot through optimizer update `1000`;
2. after the pilot passes, a separate gate for the registered first hard target
   synchronization at optimizer update `10000`.

The pilot and synchronization gate are new bounded research boundaries. They
must not be described as unrestricted training, convergence, policy
effectiveness, or held-out evaluation.

The detailed sections below are historical R3R contract context only; they do
not authorize additional R3R work. The active authorization begins at the
later `## Task` heading for R3S.

## Starting boundary and registered values

The task starts from the accepted R3Q trainer state derived from R3O:

- `10016` completed transitions and decisions;
- optimizer update `5` completed;
- target synchronization count `0`;
- no action selected after update `5`;
- online network SHA-256
  `8275fed953fb594fea0e88c50da15a862e1db6a3e296dd953dd10e048c2c3cbe`;
- target network SHA-256
  `b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb`;
- scenario seed `31001`, pilot policy seed `51001`, and exploration seed
  `61001`.

The registered runtime and optimizer settings remain unchanged: pinned Python
and Unity environments, CPU deterministic execution, replay warmup `10000`,
replay capacity `100000`, batch size `64`, `gamma=0.99`, Adam learning rate
`0.0001`, one update every `4` completed transitions, and hard target
synchronization every `10000` optimizer updates. The registered epsilon
schedule and action-mask semantics remain unchanged.

The first update is at completed transition `10000`. Therefore the exact
registered boundaries are:

| Boundary | Completed transitions/decisions | Optimizer updates | Target synchronizations |
|---|---:|---:|---:|
| R3Q starting state | `10016` | `5` | `0` |
| Continuation pilot end | `13996` | `1000` | `0` |
| First synchronization end | `49996` | `10000` | `1` |

The pilot adds `995` updates after R3Q. The first synchronization requires
`9995` additional updates after R3Q. Do not lower the registered
synchronization interval to make the boundary arrive sooner.

## Implementation boundary

### 1. Live-continuation foundation

- Add a new explicit contract, schema, bounded runner configuration, and
  validator for the long-horizon boundaries. Keep the frozen R3O/R3Q contracts,
  schemas, evidence, accepted traces, results, and checkpoints byte-identical.
- Establish a real continuation from the R3Q clean trainer boundary. R3Q stores
  trainer state but does not serialize Unity process state, so loading its
  checkpoint alone is not evidence of live Unity resume.
- Prefer deterministic replay of the accepted R3O prefix through a fresh,
  complete player copy, followed by the validated trainer-state continuation.
  A Unity resume implementation is allowed only if it proves the same boundary
  explicitly; do not call a Python-only restore a Unity resume.
- Verify the reconstructed boundary against the accepted R3O prefix before
  selecting any continuation action. Preserve transition order, observations,
  masks, rewards, episode/truncation flags, replay contents, selector state,
  optimizer state, and RNG consumption.
- Every standalone launch must use a fresh copy of the complete historical
  player directory, including the executable, `*_Data` directory, Unity player
  libraries, and sibling files. Never launch a frozen historical directory
  directly; ML-Agents profiling output must be isolated with the run.

### 2. Continuation pilot through update 1000

- Use only the registered Basic pilot seed tuple above. Do not start the other
  four policy-training seeds in this task.
- Continue through exactly `13996` completed transitions and exactly `1000`
  optimizer updates. The pilot ends at a clean boundary immediately after the
  update-1000 optimizer step and before selecting another action.
- Keep `target_sync_count == 0` and prove that the target network stayed at its
  starting hash for the entire pilot.
- Record every optimizer update decision count, online hash, loss, mean
  absolute TD error, replay accounting, epsilon sample, selector counter, and
  action/mask boundary needed to reproduce the run.
- Save a versioned checkpoint at the pilot boundary and exercise a fresh
  process restore. The restored state, next replay sample, and bounded next
  optimizer result must match an uninterrupted reference without Unity.
- Run at least two independent fresh pilot attempts or an equivalent fresh
  process differential accepted by the new contract. Preserve both raw outputs
  and the comparison result in a new ignored artifact directory.

### 3. First hard target synchronization

Start this package only after the pilot implementation and evidence pass.

- Continue the same registered lineage to exactly `49996` completed
  transitions and optimizer update `10000`. The lineage may be restored from
  the validated pilot checkpoint or reproduced by deterministic prefix replay.
- Execute exactly one hard target synchronization after the optimizer step at
  update `10000`. The target must equal the online network after the copy; the
  target must remain unchanged before that boundary; no update `10001` or second
  synchronization is authorized.
- End at the clean synchronization boundary before selecting a post-sync
  action. A separate synthetic or bounded contract test must prove the first
  legal post-sync selection path; no action may be selected and discarded in
  the live run.
- Record target-before and target-after hashes, online-before and online-after
  hashes, the synchronization count, optimizer event at update `10000`, replay
  and RNG state, and the exact stop condition.
- Save and restore a clean post-sync trainer checkpoint in a fresh process, and
  compare at least two independent fresh synchronization attempts under the
  new contract. The synchronization result must be deterministic at the raw
  result/checkpoint/summary boundary required by that contract.

## Validator and contract requirements

- Preserve generic schema validation before relational validation and preserve
  actionable failure types, messages, and ordering where observable.
- Leave the existing milestone validators specialized and unchanged for R3O,
  R3Q, and all frozen historical evidence. Do not turn
  `UPDATE_PREFIX_FIELDS` into filename inference or silently broaden its four
  historical ordinal mappings.
- Add explicit fields for the long-horizon update list, sync event list,
  target-before/after identity, continuation prefix, final clean boundary, and
  post-boundary action policy. The new validator must reject an early, missing,
  repeated, or misordered synchronization and any target drift before it.
- Do not build an unrestricted training framework. The new runner remains a
  bounded, contract-driven continuation with explicit end counts and registered
  seeds/settings.
- Retain the existing R3O/R3Q acceptance paths and prove that their schemas,
  hashes, failure cases, and results remain valid without modification.

## Invariants

Preserve the network architecture, observation bytes and layout, branch action
semantics, legality masks, reward and episode boundaries, replay representation
and accounting, optimizer algorithm, update timing, target-sync timing, seeds,
RNG ownership and consumption order, deterministic CPU settings, checkpoint
encoding, clean-boundary rules, and all registered runtime values. Do not
change the Unity scene, gameplay mechanics, player settings, or accepted
research contracts to make the longer run easier.

## Acceptance criteria

- The new contracts and schemas are explicit, hash-bound where required, and do
  not modify any R3O/R3Q frozen file.
- The continuation method reproduces the accepted R3O prefix through transition
  `10016` and proves a clean, no-pending-decision handoff into the pilot.
- The pilot produces exactly `13996` transitions, `1000` optimizer updates,
  zero target synchronizations, finite recorded metrics, valid replay
  accounting, exact schedule/epsilon/selector relationships, and no final
  post-update action.
- Independent pilot attempts and checkpoint restore reproduce the contract's
  required raw bytes, hashes, state digests, next sample, and bounded next
  update.
- The synchronization gate produces exactly `49996` transitions, `10000`
  optimizer updates, and one target synchronization at the registered boundary;
  it proves target equality after the copy, target stability before it, and no
  update or synchronization beyond the boundary.
- New negative tests reject prefix drift, update-count drift, early/repeated or
  missing synchronization, target-before drift, target-after mismatch, dirty
  checkpoint state, selector/RNG drift, pending decisions, and discarded
  post-boundary actions.
- Existing focused and complete Python suites pass, the affected Unity/LLAPI
  integration path passes in the pinned environment, and the configured
  read-only review covers the new implementation and evidence.
- Fresh ignored artifacts retain commands, versions, seeds, contract hashes,
  raw traces, checkpoints, result summaries, comparison logs, and any failed or
  rejected attempts. No profiling output is written into a frozen player
  directory.
- The final report distinguishes software-contract and deterministic replay
  evidence from training effectiveness. It does not claim convergence,
  held-out success, five-seed completion, export parity, ROCm training,
  strategic combat, or a useful policy.

## Explicit exclusions and stop rules

- Do not alter the registered sync interval, update interval, learning rate,
  gamma, replay capacity, warmup, batch size, epsilon schedule, action space,
  or seeds.
- Do not run optimizer update `10001`, a second target synchronization, the
  five-seed training campaign, held-out evaluation, ONNX export, ROCm training,
  strategic combat, the gradual-motion variant, or the research reflex.
- Do not resume Unity or claim live resumption until the continuation boundary
  is directly verified. Do not select an action after either final boundary and
  omit it from the trace.
- Do not overwrite accepted evidence, regenerate frozen artifacts, weaken
  validation, lower thresholds, or add a generic/unbounded training runner.
- Do not commit, push, open a PR, deploy, publish, or mutate third-party
  systems without separate explicit authorization.

## Task

Status: complete and accepted on 2026-09-09. The R3S result is retained under
the ignored artifact boundary and recorded in [`docs/evidence/R3S.md`](docs/evidence/R3S.md).
This entry authorizes no further work; a new bounded task is required.

### R3S — Live Unity trajectory resumption and learned-policy export parity

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

## Starting boundary and registered values

The task starts from the accepted R3R first-synchronization clean boundary.
The implementation must load and validate the existing R3R artifacts rather
than manually reconstructing their values:

- contract:
  [`Research/trainer/bdq-long-horizon-contract-v1.json`](Research/trainer/bdq-long-horizon-contract-v1.json),
  schema version `quickdraw.bdq-long-horizon.v1`;
- accepted result:
  `Artifacts/Experiments/r3r-long-horizon-synchronization-final/result.json`,
  accepted SHA-256
  `644a6c3c295f3c5a5c10f1a6c6f36a034e84dfffcecc2a0c4e133fd83034c1b7`;
- accepted canonical trace SHA-256:
  `6605bb688cf4a7c3c4b5478e5042746a0bcb17b6d698676dd98ee2cb16ce3bff`;
- accepted checkpoint state SHA-256:
  `bb7bc2a0f52f20adc6fd13f49ea3057a8e4f1af1a94be3ee4b33f29bf459da27`;
- completed transitions and decisions: `49,996`;
- completed optimizer updates: `10,000`;
- target synchronizations: `1`;
- last selected action: at completed-transition count `49,995`;
- pending trainer agent IDs: `[]`;
- no post-synchronization live action has been selected;
- target-before synchronization SHA-256:
  `b605debdd6073caa41a95d636bcf20b35d000dc959b06d5cbe585cac0bb433bb`;
- online network after update 10,000 and target network after the copy:
  `5e455aac0264f98a364ec9d296671e91539fea0522d48f438b416950983f747f`;
- replay capacity: `100,000`; replay size and cursor: `49,996`; frame
  references: `399,968`; and accounted storage remains below the registered
  `4 GiB` ceiling; and
- the accepted result has two independent fresh workers and fresh
  Python-restorer parity.

The registered runtime and environment contract remain unchanged:
Python `3.11.13`, Unity ML-Agents `4.0.0`, `mlagents-envs==1.1.0`,
`numpy==1.23.5`, `torch==2.12.0+cpu`, deterministic CPU execution with one
Torch thread and one interop thread, one agent, behavior
`QuickDrawResearchBasic`, float32 HWC observations of shape
`[84,84,4]`, and discrete branches `[3,2]`. Keep scenario seed `31001`,
policy seed `51001`, and exploration seed `61001`. Preserve the registered
replay, optimizer, epsilon, mask, reward, episode, and truncation semantics.

If the accepted R3R result, checkpoint, or required player provenance is
missing or hash-mismatched, fail closed and stop. Do not silently recreate a
different starting state.

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
