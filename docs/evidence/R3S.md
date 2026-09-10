# R3S — Live Unity trajectory resumption and learned-policy export parity

Status: accepted on 2026-09-09 in the pinned Windows CPU environment.

R3S is a bounded reproducibility and serving-boundary gate. It starts from the
accepted R3R synchronization artifacts, keeps one run-owned Unity player alive
while a fresh Python trainer process restores the trainer checkpoint, completes
exactly one post-resume action, and then exports the accepted R3R online network
to ONNX for CPU inference parity. It is not training-effectiveness, convergence,
held-out, or production-readiness evidence.

## Contract and starting boundary

- Contract: `Research/trainer/bdq-live-resume-export-contract-v1.json`
  (`a03481a7a6b3b23457154d51d14a1b6dbcfeeae08b3f67b51a2371b333b489ee`).
- Contract schema SHA-256:
  `5795c4bb08d23bd861005b33e27f5da6bcaab37d61d9cecf66f9d265de524a45`.
- Result schema SHA-256:
  `d49568e6aba96251ad982df03ae0405b4a78987db3a49f01fe7b7b9a10fff602`.
- Accepted R3R result SHA-256:
  `644a6c3c295f3c5a5c10f1a6c6f36a034e84dfffcecc2a0c4e133fd83034c1b7`.
- Accepted R3R checkpoint state SHA-256:
  `bb7bc2a0f52f20adc6fd13f49ea3057a8e4f1af1a94be3ee4b33f29bf459da27`.
- Accepted post-sync online/target network SHA-256:
  `5e455aac0264f98a364ec9d296671e91539fea0522d48f438b416950983f747f`.
- Accepted player manifest SHA-256:
  `83cb3b701e842d26e732be7f01ba6559dbc360c8cad53e10846b970ec1c7429d`
  (187 files, 104,896,089 bytes).

The starting boundary was reproduced at 49,996 transitions/decisions, 10,000
optimizer updates, one target synchronization, and no pending decision or
post-boundary action. The accepted R3R trace and checkpoint raw hashes matched
in both fresh attempts.

## Live handoff result

Raw output is retained under the ignored directory
`Artifacts/Experiments/r3s-live-resume-export/acceptance/`.

- Result SHA-256:
  `cff5ffb63ebfc0b442216ba9cf10d86a150060cf10817f74ed8de572b8659151`.
- Both attempts have canonical SHA-256
  `218156c2592f9a27dd937afbf2f5491f893c827468711ab4877e4c91098e2d11`.
- Each attempt launched one complete copied player, reset once, stepped 49,996
  times before handoff, applied one resumed action, and stopped at 49,997
  steps. The player PID plus Windows creation marker was identical before and
  after each handoff, while the restored trainer had a distinct process
  identity. The process-leak check passed after both attempts.
- The resumed action was `[0, 0]`, with reward `-0.009999999776482582`, and the
  completed transition was index `49,996` (the 49,997th transition). No
  optimizer update 10,001 or second target synchronization occurred. The two
  post-resume observations matched at SHA-256
  `f8ba172eb1f36ca30532203466326599bbe4eaeac9e90159160a679d49cd100a`.
- The observed handoff event sequence was the contract’s eleven-event sequence:
  boundary verification, checkpoint save, trainer detachment without action,
  fresh trainer start and restore, decision transfer, action selection and
  application, one Unity step, transition completion, and final clean-boundary
  verification.

## ONNX parity result

- Accepted ONNX model SHA-256:
  `cfc5d5e803193869558c1134586e172e069ef7ec016bd7c35d8a7d620538cc11`.
- Export metadata SHA-256:
  `0a065ecbcf9fdde6bf330a0cece01793b9930d2d16e6c299732bd3a70b79bc0b`.
- The graph uses opset 17, input `observations` with shape `[N,84,84,4]` and
  float32 values, and ordered float32 outputs `branch_0_q_values [N,3]` and
  `branch_1_q_values [N,2]`.
- The 64-row corpus contains 63 accepted-checkpoint rows covering all current
  mask patterns and one post-resume observation. Corpus SHA-256:
  `ada0023412cf8fa08ff4570238996c190a7833d92a0bf9d5e3175d6c419aae6d`.
- Python/ONNX maximum absolute Q-value difference was
  `2.384185791015625e-07`, below the registered `1e-5` limit. All outputs were
  finite, masked branch actions matched exactly, and single-item versus batch
  inference matched.
- Two fresh CPU inference processes produced identical canonical output and
  action hashes:
  `547ed3d43d17b902ad7cc4143e706aa179aec3eaf1e0cf41c333242c99021519` and
  `aaf97964235b3e20353681f7d7f4d9ea698b70438d7633898024eda304c517b2`.

## Verification and limitations

The pinned command was:

```powershell
& $python -B Research\trainer\run_bdq_live_resume_export_smoke.py `
  --output Artifacts\Experiments\r3s-live-resume-export\acceptance
```

The runner’s result validator was rerun independently from the retained raw
artifacts after completion. The focused R3S suite passed 30 tests, and the
existing R3R/checkpoint compatibility set passed 68 tests. The complete
trainer suite passed 328 tests with the repository's 100 pre-existing
ML-Agents protobuf deprecation warnings suppressed for the run. A prior
operator-aborted attempt caused by a Windows venv-wrapper identity audit defect
is retained under
`Artifacts/Experiments/r3s-live-resume-export/rejected-wrapper-audit/`;
it is rejected evidence, not part of the accepted result.

This record demonstrates live-process continuity and exported-inference
software parity for the registered one-seed boundary only. It does not claim
policy effectiveness, convergence, generalization, held-out success, a useful
policy, unrestricted training, ROCm inference/training, or final checkpoint
selection.
