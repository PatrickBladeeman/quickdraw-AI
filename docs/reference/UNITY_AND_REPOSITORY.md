# Unity and repository reference

## Verified Unity baseline

- Editor: Unity `6000.0.57f1` revision `b7b9860b7bbd`.
- Render pipeline: URP `17.0.4`, with tracked renderer and pipeline assets under
  `Assets/_Project/Settings/`.
- Input System: `1.14.2`; Active Input Handling is `Both`.
- ML-Agents Unity package: `com.unity.ml-agents` `4.0.0`.
- Locked inference dependency: `com.unity.ai.inference` `2.2.1`.
- Newtonsoft JSON: `3.2.1`.
- ProBuilder: `6.0.7`.
- Animation Rigging: `1.3.0`.
- Cinemachine: `3.1.2`.
- Unity Test Framework: `1.5.1`.

`Packages/manifest.json`, `Packages/packages-lock.json`, and
`ProjectSettings/ProjectVersion.txt` are the owning version sources. Do not use
this summary to justify an opportunistic dependency update.

## Editor and player settings

The tracked settings establish:

- VSync off in both configured quality levels;
- Incremental GC on;
- Visible Meta Files;
- Force Text asset serialization;
- Enter Play Mode Options enabled with Domain Reload off and Scene Reload on;
- `runInBackground` enabled for the standalone LLAPI player.

Domain Reload off means static and singleton state must reset explicitly. The
logger and ML-Agents sensor lifecycle tests cover known instances of this risk.
`runInBackground` was enabled for R3M so an unfocused standalone worker would
not pause; normal graphics remained required for the visual observation.

## Repository boundaries

Project-owned Unity implementation belongs under `Assets/_Project/`. Research
contracts, Python sources, schemas, and runbooks belong under `Research/`.
Generated research output belongs under ignored `Artifacts/Experiments/`.

Track, when changed by an authorized task:

- source and tests;
- Unity scenes, prefabs, settings, and every required `.meta` file;
- package manifest and lock;
- reproducibility contracts, schemas, scripts, and documentation.

Do not track Unity/IDE caches, local environments, raw logs, disposable builds,
large checkpoints, model weights, or non-redistributable assets. See
[`ARTIFACT_POLICY.md`](ARTIFACT_POLICY.md).

## Text and line endings

Historical documentation proposed explicit LF rules for C#, Unity text assets,
Markdown, JSON, YAML, and citation files. The current tracked `.gitattributes`
contains Git LFS rules for binary asset extensions but does **not** encode those
text EOL rules. Therefore:

- preserve existing line endings during narrow edits;
- inspect `git diff --check` and the final diff for whole-file churn;
- do not describe the proposed LF policy as repository-enforced until an
  authorized configuration task adds and verifies it.

## Local Unity CLI qualification

Unity CLI `1.0.0-beta.5` has been used as local developer tooling to recognize
and structurally verify this Unity project and to reproduce one focused NUnit
result. It is not a tracked project dependency, and the experimental
`com.unity.pipeline` package is not installed.

Raw Unity Editor stderr may contain authentication-bearing command-line
arguments. Treat it as sensitive: do not paste or preserve the full stream when
only a test result or diagnostic excerpt is needed.

## Environment runbooks

- CPU, Python 3.11/ROCm compatibility, and fixed-policy parity:
  [`Research/environment/README.md`](../../Research/environment/README.md)
- Communicator smoke and CPU reference:
  [`Research/smoke/README.md`](../../Research/smoke/README.md)
- Basic environment baseline:
  [`Research/basic/README.md`](../../Research/basic/README.md)
- BDQ and LLAPI runners:
  [`Research/trainer/README.md`](../../Research/trainer/README.md)

Those domain runbooks own executable commands. Milestone outcomes belong in
[`docs/evidence`](../evidence/README.md).
