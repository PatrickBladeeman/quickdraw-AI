# R3R — Historical task specification

> Historical, completed specification retired from TASK.md on 2026-09-10.
> It grants no current authority; see [TASK.md](../../../TASK.md).
> Exact accepted results and rejected attempts belong in [R3R evidence](../../evidence/R3R.md).

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

## Starting boundary

The accepted R3Q input state, registered settings, and pilot/synchronization
counts are retained in [R3R evidence](../../evidence/R3R.md) and its linked
frozen contract. These were task inputs and acceptance requirements, not
new authorization.

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

- Use only the Basic pilot seed tuple in the linked frozen contract. Do not start the other
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
