# Research_Basic environment baselines

This directory is the R2A environment-only validation surface. It does not train a model. The Unity scene provides one deterministic visual agent, and this runner exercises random and scripted policies through the same ML-Agents low-level `ActionTuple` interface that a learned policy will use later.

The actual observation is uncompressed float32 HWC `[84, 84, 4]`: four Rec. 601 grayscale frames ordered oldest to newest. The room uses a registered directional key light and lit high-contrast materials; the compact cyan reticle is unlit and remains aligned with the hitscan. At reset, Unity captures one post-reset image and copies it into all four channels. If Domain Reload off exposes a missing first-reset ordering, the sensor starts a real deterministic episode and recaptures its post-reset frame before writing an observation. The policy receives no vector observation, target coordinate, object identifier, scene matrix, or debug label.

Every action is a concurrent two-branch tuple: movement `[Stay, Left, Right]` and combat `[Idle, Shoot]`; utility is fixed to `Idle`. Movement is applied once on each 10 Hz policy decision, then `Shoot` uses the same center-camera ray used by the fixed crosshair. ML-Agents holds the accepted tuple during the four intervening physics steps without repeating one-shot mechanics.

Immediately before a decision-limit `EpisodeInterrupted()`, Unity sends one
strict `quickdraw.basic-truncation-mask.v1` side-channel message containing the
environment-authored action-unavailability masks for the final state. This is
used by the direct BDQ collector because truncated transitions bootstrap while
true terminals do not. The message contains only contract state needed to
validate the mask; Python does not inspect scene objects or infer legality.

The tracked `basic-contract-v1.json` fixes geometry, timing, reward, reset, target sampling, and baseline-policy behavior. Both baselines emit `quickdraw.basic-episode.v1` episode records validated by `Research/schemas/basic-baseline-trace.schema.json`; later learned policies must emit that same episode shape.

Build the dedicated standalone from the tracked saved scene. Scene regeneration
is a separate explicit editor action; `BuildWindows` does not rewrite the scene
before serialization:

```powershell
& 'C:\Program Files\Unity\Hub\Editor\6000.0.57f1\Editor\Unity.exe' `
  -batchmode -nographics -quit `
  -projectPath 'C:\projects\quickdraw-AI' `
  -executeMethod QuickDraw.Editor.ResearchBasicBuild.BuildWindows `
  -quickdrawBasicOutput 'Artifacts\Experiments\r2a-basic\build\QuickDrawResearchBasic.exe' `
  -logFile 'Artifacts\Experiments\r2a-basic\build.log'
```

Use the registered Python 3.11 ML-Agents 1.1 environment. Visual capture requires a graphics device, so the runner intentionally starts the player with `no_graphics=False`:

```powershell
$python = 'Artifacts\Experiments\.venvs\r1f-cpu-py311\Scripts\python.exe'
$basicPlayer = 'Artifacts\Experiments\r2a-basic\build\QuickDrawResearchBasic.exe'

& $python Research\basic\run_basic_baseline.py `
  --env $basicPlayer --policy scripted `
  --output Artifacts\Experiments\r2a-basic\scripted-1

& $python Research\basic\run_basic_baseline.py `
  --env $basicPlayer --policy scripted `
  --output Artifacts\Experiments\r2a-basic\scripted-2 `
  --compare-to Artifacts\Experiments\r2a-basic\scripted-1\trace.json
```

Repeat those two commands with `--policy random` and distinct output directories. A comparison pass means actions, observation hashes, rewards, episode ends, and episode summaries matched across fresh standalone processes for that policy and its registered seed.
