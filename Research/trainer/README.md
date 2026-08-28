# R3A-R3M BDQ foundation, direct LLAPI collection, and exploration schedule

This directory contains QuickDraw's bounded Branching Double DQN implementation.
R3A freezes tensors, replay, masks, the visual network, Double-DQN targets, and
Huber loss. R3B freezes the optimizer and update schedule. R3C records the
superseded high-level ML-Agents trajectory experiment. R3D replaces that
experiment with synchronous `DecisionSteps`/`TerminalSteps` collection. R3E
adds deterministic mask-safe epsilon-greedy collection below replay warmup.
R3F reaches the exact production warmup and performs one CPU update from real
Unity transitions. R3G extends the same seeded run by four transitions and
proves the second scheduled CPU update. R3H preserves that entire prefix, then
uses the twice-updated online network for one legal masked-greedy action and
completes its Unity transition. R3I freezes and unit-tests the production
epsilon schedule without launching Unity or opening another optimizer update.
R3J then drives every action in a bounded two-process Unity run through one
continuous production scheduled selector and completes one live scheduled
handoff after update 2 without opening update 3.
R3K preserves that complete 10,005-transition prefix, consumes exactly three
more scheduled actions, and stops when optimizer update 3 completes at decision
10,008 without selecting a post-update action.
R3L preserves all 10,008 R3K transitions, then deliberately bypasses the
production schedule for one epsilon-zero diagnostic handoff from the update-3
online network. It completes that legal masked-greedy action and stops before
update 4.
R3M instead returns to R3K's uninterrupted production trajectory, consumes
scheduled selections at counts 10,008 through 10,011, and stops exactly when
optimizer update 4 completes at decision 10,012.

The tracked contract chain is:

- `bdq-foundation-contract-v1.json`: historical R3A foundation;
- `bdq-optimizer-contract-v1.json`: historical R3B optimizer contract;
- `bdq-llapi-contract-v1.json`: current R3D direct-collection and
  truncation-mask contract.
- `bdq-epsilon-collection-contract-v1.json`: R3E's hash-bound, fixed-epsilon,
  exactly-1,000-transition collection contract.
- `bdq-warmup-update-contract-v1.json`: R3F's hash-bound, exactly-10,000-
  transition production-warmup and first-update contract.
- `bdq-two-update-contract-v1.json`: R3G's hash-bound, exactly-10,004-
  transition recurring-update contract.
- `bdq-post-update-handoff-contract-v1.json`: R3H's hash-bound R3G-prefix plus
  one post-update masked-greedy transition contract.
- `bdq-epsilon-schedule-contract-v1.json`: R3I's hash-bound, stateless linear
  production epsilon-schedule contract.
- `bdq-scheduled-epsilon-handoff-contract-v1.json`: R3J's hash-bound,
  exactly-10,005-transition continuous scheduled-selector handoff contract.
- `bdq-third-update-contract-v1.json`: R3K's hash-bound, exactly-10,008-
  transition continuous scheduled-selector third-update contract.
- `bdq-third-update-greedy-handoff-contract-v1.json`: R3L's hash-bound R3K
  prefix plus one update-3 masked-greedy transition contract.
- `bdq-fourth-update-contract-v1.json`: R3M's hash-bound, exactly-10,012-
  transition continuous scheduled-selector fourth-update contract.

`quickdraw_bdq` now contains only the reusable learning core and direct LLAPI
boundary:

- `replay.py`: immutable validated transitions and seeded uniform replay;
- `network.py`: the three-convolution visual encoder and dueling `[3,2]`
  branch heads;
- `action_space.py`: branch/joint mapping and strict mask-aware selection;
- `targets.py`: per-branch Double-DQN targets and averaged Huber loss;
- `optimizer.py`: online/target networks, Adam, replay, and exact counters;
- `exploration.py`: the validated stateless linear production epsilon schedule;
- `llapi.py`: behavior validation, online-network action selection, one pending
  decision per agent, direct replay completion, and strict truncation-mask
  side-channel ingestion. It also exposes the fixed seeded epsilon-greedy
  selector used by R3E through R3G and R3I-R3M's scheduled selector. At epsilon
  `1.0`, both preserve the exact exploration RNG sequence without evaluating
  unused network Q-values.

The former `Trainer`, `Policy`, `Trajectory`, settings, plugin-registration,
YAML, and next-mask-registry scaffolding has been removed. `pyproject.toml`
therefore registers no `mlagents.trainer_type` entry point and depends only on
`mlagents-envs`, NumPy, and PyTorch.

For each agent, the runner stores `(observation, action, current masks)` when a
decision is sent. When that agent next appears, it completes exactly one replay
transition with the delivered reward and next observation. A `DecisionStep`
supplies the next masks for ordinary continuation. A true terminal uses an
irrelevant all-available sentinel because it does not bootstrap. A decision-limit
truncation receives the authoritative final-state mask from Unity over the
dedicated `quickdraw.basic-truncation-mask.v1` side channel; Python never infers
that mask from privileged scene state.

Install the editable package in the isolated Python 3.11 environment:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$python = 'Artifacts\Experiments\.venvs\r1f-cpu-py311\Scripts\python.exe'
& $python -B -m pip install --no-deps -e Research\trainer
```

Run the focused trainer suite:

```powershell
& $python -B -m pytest -p no:cacheprovider Research\trainer
```

Build the already-saved `Research_Basic` scene, then run the real two-process
gate:

```powershell
& 'C:\Program Files\Unity\Hub\Editor\6000.0.57f1\Editor\Unity.exe' `
  -batchmode -nographics -quit `
  -projectPath 'C:\projects\quickdraw-AI' `
  -executeMethod QuickDraw.Editor.ResearchBasicBuild.BuildWindows `
  -quickdrawBasicOutput 'Artifacts\Experiments\r3d-llapi\build\QuickDrawResearchBasic.exe' `
  -logFile 'Artifacts\Experiments\r3d-llapi\build.log'

& $python Research\trainer\run_bdq_llapi_smoke.py `
  --env Artifacts\Experiments\r3d-llapi\build\QuickDrawResearchBasic.exe `
  --output Artifacts\Experiments\r3d-llapi\live-smoke
```

Each fresh process collects two episodes. The unchanged online network greedily
finishes the first. The second moves left four times, idles through decision
300, and ends as an interrupted truncation at slot `-4`, whose Unity-authored
movement mask is `[false,true,false]`. Every one of the 302 decisions becomes
one replay transition. The gate requires exact trace equality, zero optimizer
updates, zero target synchronizations, and unchanged online/target weight
hashes.

Run the R3E collection gate against the same saved-scene player:

```powershell
& $python Research\trainer\run_bdq_epsilon_collection_smoke.py `
  --env Artifacts\Experiments\r3d-llapi\build\QuickDrawResearchBasic.exe `
  --output Artifacts\Experiments\r3e-epsilon-collection\acceptance
```

R3E fixes epsilon at the registered starting value `1.0` and uses exploration
seed `61001`; decay is deliberately closed. Each fresh process completes
exactly 1,000 transitions across resets, stops before issuing a replacement
action, and therefore leaves no pending decision. The accepted local pair
completed 18 episodes, exercised all six action tuples, handled one truncation,
performed zero optimizer updates or target synchronizations, preserved both
networks, and produced byte-identical traces.

Run the R3F production-warmup and first-update gate:

```powershell
& $python Research\trainer\run_bdq_warmup_update_smoke.py `
  --env Artifacts\Experiments\r3e-epsilon-collection\build-final\QuickDrawResearchBasic.exe `
  --output Artifacts\Experiments\r3f-warmup-update\acceptance
```

Each accepted fresh process collected exactly 10,000 complete transitions,
crossed 215 episode resets, handled three truncations, and exercised all six
action tuples. No update occurred through transition 9,999. Transition 10,000
opened exactly one registered batch-64 Adam update with loss
`0.01628389209508896` and mean absolute TD error `0.06243317946791649`. The
online weights changed, the target weights remained frozen, target-sync and
pending-decision counts stayed zero, and the two complete traces matched byte
for byte.

To watch one diagnostic run in the Unity Editor, open `Research_Basic` but
leave the Editor out of Play Mode, then start Python:

```powershell
& $python Research\trainer\run_bdq_warmup_update_smoke.py `
  --watch `
  --output Artifacts\Experiments\r3f-warmup-update\editor-watch
```

When Python reports that it is listening on port `5004`, press Play in Unity.
The runner forces `Time.timeScale` to `1`, targets 60 frames per second, and
prints the completed transition count, current episode and episode decision,
selected action, reward, replay size, optimizer-update count, and target-sync
count every 100 transitions. `--progress-interval N` changes that terminal
reporting interval. The run stops after transition 10,000 and its first update;
stop Play Mode manually afterward.

The same one-run diagnostic can launch a visible standalone player:

```powershell
& $python Research\trainer\run_bdq_warmup_update_smoke.py `
  --watch `
  --env Artifacts\Experiments\r3e-epsilon-collection\build-final\QuickDrawResearchBasic.exe `
  --output Artifacts\Experiments\r3f-warmup-update\standalone-watch
```

Both watch forms write one validated trace only. They are explicitly
observational and never produce the two-fresh-process `result.json` required by
the unchanged R3F acceptance gate. A local standalone watch validation completed
all 10,000 transitions at time scale 1, performed the same single update, and
produced trace SHA-256
`aee36f7bc5c2e2202e2738709c021826878de717d22b91345001dafd8599f0b2`,
byte-identical to each accepted worker trace, without creating `result.json`.

Run the R3G second-update gate against the same saved-scene player:

```powershell
& $python Research\trainer\run_bdq_two_update_smoke.py `
  --env Artifacts\Experiments\r3e-epsilon-collection\build-final\QuickDrawResearchBasic.exe `
  --output Artifacts\Experiments\r3g-two-update\acceptance
```

Each accepted fresh process completed exactly 10,004 transitions. The first
10,000 transitions and first-update evidence exactly preserve R3F. Update 2
opened at decision 10,004 with loss `0.014819225296378136`, mean absolute TD
error `0.06711231172084808`, and online SHA-256
`6248f286191da322a52ad0c97f569d30ecd49a1c86e9810bda4cb96ccc6b9471`.
The target remained frozen, pending-decision and target-sync counts stayed zero,
and the two serialized traces matched SHA-256
`157cc826d99696fa5c137b596e8eafd04b4abba520c8af5d93b7355b8bdc5576`.

Run the R3H post-update policy-handoff gate:

```powershell
& $python Research\trainer\run_bdq_post_update_handoff_smoke.py `
  --env Artifacts\Experiments\r3e-epsilon-collection\build-final\QuickDrawResearchBasic.exe `
  --output Artifacts\Experiments\r3h-post-update-handoff\acceptance
```

Each accepted process preserves all 10,004 R3G transitions and both exact
optimizer results. At decision 10,004, epsilon switches from the frozen random
prefix to `0.0` for one decision only. The updated online network evaluates the
live observation and masks, chooses masked argmax action `[2,1]`, and completes
transition 10,005. The same observation is evaluated by the frozen target;
their maximum absolute Q-value difference is `0.08040044084191322`. The action
is legal under movement mask `[false,true,false]`, no third update opens, no
target synchronization occurs, and no decision remains pending. Two fresh
processes produced byte-identical serialized traces with SHA-256
`4341790871e0b5e3a990923601b45c052e9fb85e1e8ca20ae179421bb7977a87`.

R3I derives training epsilon solely from the number of completed replay
transitions. Epsilon remains `1.0` through transition 10,000, decays linearly
over the next 100,000 transitions, reaches `0.1` at transition 110,000, and is
clamped there. The schedule has no mutable state; the caller supplies the
optimizer controller's completed-transition count to the scheduled selector.

Run the R3J scheduled-epsilon live handoff gate:

```powershell
& $python Research\trainer\run_bdq_scheduled_epsilon_handoff_smoke.py `
  --env Artifacts\Experiments\r3e-epsilon-collection\build-final\QuickDrawResearchBasic.exe `
  --output Artifacts\Experiments\r3j-scheduled-epsilon-handoff\acceptance
```

Each accepted process uses one scheduled selector continuously for all 10,005
actions. Counts 0 through 10,000 use epsilon `1.0`; counts 10,001 through
10,004 use the first four decay values. The exact 10,004-transition R3G prefix,
two optimizer results, online hashes, and frozen target hash remain unchanged.
At completed-transition count 10,004, epsilon is `0.999964` and the continuous
seed-`61001` stream selects legal exploratory action `[0,0]` under movement mask
`[false,true,false]`. The action completes transition 10,005. Two fresh traces
match byte-for-byte with SHA-256
`135d6a30c8526cd7422f9e30ff21cd997bd05a0ccbcdc5efd75b6fe1182d04a7`;
the canonical trace SHA-256 is
`5e3a8ea3d2c0f0afb87fd87f92f6bf90036a6a95fc3f6124ccc0910ca07aa906`.

Run the R3K scheduled third-update gate:

```powershell
& $python Research\trainer\run_bdq_third_update_smoke.py `
  --env Artifacts\Experiments\r3e-epsilon-collection\build-final\QuickDrawResearchBasic.exe `
  --output Artifacts\Experiments\r3k-third-update\acceptance
```

Each accepted process preserves all 10,005 R3J transitions, then selects only
at completed counts 10,005, 10,006, and 10,007 with epsilons `0.999955`,
`0.999946`, and `0.999937`. Completing transition 10,008 triggers optimizer
update 3 with loss `0.008735351264476776`, mean absolute TD error
`0.06769348680973053`, and online hash
`4f78e397e87ad6cea1ada78d49dea808337c401f6478970d1a4439065743775b`.
The target remains frozen, no decision remains pending, and no action is selected
after update 3. Two fresh serialized traces match byte-for-byte with SHA-256
`4e4733dd5e5cbfbd7daa21f6d2ad8c48981b4369769d8df000b709e9c115dde4`;
the canonical trace SHA-256 is
`c3fafe259dfc03d69e06c758af0c2ba4df3b5da3322d325a5e361cdcf3a4ff02`.

Run the R3L update-3 masked-greedy handoff gate:

```powershell
& $python Research\trainer\run_bdq_third_update_greedy_handoff_smoke.py `
  --env Artifacts\Experiments\r3e-epsilon-collection\build-final\QuickDrawResearchBasic.exe `
  --output Artifacts\Experiments\r3l-third-update-greedy-handoff\acceptance
```

Each accepted process preserves R3K's exact 10,008-transition scheduled prefix
and all three optimizer events. At completed-transition count 10,008, R3L does
not consume the production schedule's epsilon `0.999928`; it instead performs
one diagnostic epsilon-zero evaluation of the live observation with the
update-3 online network and frozen target. The legal masked online argmax is
`[2,1]`, completing transition 10,009 with no pending decision, fourth update,
or target synchronization. The maximum online-versus-target Q delta is
`0.08219506591558456`. Two independent fresh-process traces have canonical
SHA-256 `19d5681bc78d8b1c7df0bef0e4ea3a5a32f757629428e11fa2961c5cafd581e3`
and serialized SHA-256
`1334f396fa0445cf4c4563c28ef22e8fa8cfc8ce383687b3c2918d1515bc4665`.

If valid workers finish in separate parent attempts because a later Unity
process times out, compare only the completed trace files and write a fresh
result with the recovery-validation mode:

```powershell
& $python Research\trainer\run_bdq_third_update_greedy_handoff_smoke.py `
  --output Artifacts\Experiments\r3l-third-update-greedy-handoff\accepted-pair `
  --first-trace <first-complete-trace.json> `
  --second-trace <second-complete-trace.json>
```

This path still validates both full traces against the frozen contract and
requires distinct files, object equality, and raw-byte equality. Failed or
partial workers never count toward `fresh_process_count`.

Build the R3M player with background execution enabled, then run the scheduled
fourth-update gate:

```powershell
$unity = "$env:LOCALAPPDATA\Unity\bin\unity.exe"
& $unity --non-interactive build . `
  --target StandaloneWindows64 `
  --execute-method QuickDraw.Editor.ResearchBasicBuild.BuildWindows `
  --args '-quickdrawBasicOutput Artifacts/Experiments/r3m-fourth-update/build/QuickDrawResearchBasic.exe' `
  --log-file Artifacts/Experiments/r3m-fourth-update/build.log `
  --allow-dirty-build --no-tail

& $python Research\trainer\run_bdq_fourth_update_smoke.py `
  --env Artifacts\Experiments\r3m-fourth-update\build\QuickDrawResearchBasic.exe `
  --output Artifacts\Experiments\r3m-fourth-update\acceptance
```

`ProjectSettings/ProjectSettings.asset` keeps `runInBackground` enabled so a
standalone LLAPI worker does not pause when its window loses focus. Graphics
remain enabled and R3M passes no standalone-player arguments; the camera sensor
therefore retains the normal renderer path. Each accepted worker preserves
R3K's exact 10,008-transition prefix, selects at completed counts 10,008 through
10,011 with epsilons `0.999928`, `0.999919`, `0.99991`, and `0.999901`, and
completes update 4 at decision 10,012. Update 4 has loss
`0.0085072573274374`, mean absolute TD error `0.06249994412064552`, and online
hash `a8356df1531b99a42966578c6fd784cd384c8bcd3d3c3092124df13b2587268f`.
The target remains frozen, no decision remains pending, and no action is
selected after update 4. Two fresh traces have canonical SHA-256
`cd2fa70672432e74c16c34c0525035953961ac3845cbe3362e061373cf48a940`
and byte-identical serialized SHA-256
`762fd1d090dc88529f3ad86cd0ad87080aff6494587c10223ae89118bb910a51`.
The contract SHA-256 is
`0a6f209d93ef6d522a53f24807d4ce48e6e820a344905e9762583bbe13a72dbb`,
and the accepted result SHA-256 is
`b79a1ba8ab0d23964c225a9b33236226b1c033f8e3de972d61e759f90d890d67`.

R3M also supports the same fail-closed completed-trace comparison pattern:

```powershell
& $python Research\trainer\run_bdq_fourth_update_smoke.py `
  --output Artifacts\Experiments\r3m-fourth-update\accepted-pair `
  --first-trace <first-complete-trace.json> `
  --second-trace <second-complete-trace.json>
```

Five runs of the older background-disabled player timed out at
`environment.step()`. A `-batchmode` experiment completed but changed the first
camera observation and was rejected by the canonical R3K-prefix gate. Those
negative results do not count toward acceptance and no threshold was weakened.

R3D and R3E are collection evidence. R3F, R3G, R3K, and R3M are four minimal scheduled
learning operations on real Unity experience. R3H is the first live proof that
the resulting online weights drive a greedy action. R3I is the schedule unit
gate, and R3J proves its bounded live counter/RNG/mask integration. Because the
R3J action is exploratory, it is not evidence that learned weights chose that
action or that a useful policy exists. R3K proves only that the same scheduled
loop reaches update 3 and stops cleanly. R3L proves that the update-3 weights
reach one live greedy selection; it does not prove the third update changed the
chosen action or that the policy is effective. R3M proves only that the
uninterrupted production loop reaches update 4 and stops cleanly. Extended
decay rollout, update 5, target
synchronization, checkpoint/resume, ONNX export, ROCm training, learned-policy
evaluation, gradual motion, strategic combat, reflexes, and LLM work remain
outside this slice.
