# R3I: production epsilon-schedule unit gate

Status: completed and pushed in
`8d999d4b1ee566c5ea66d40c745086db40c7f05f` on 2026-08-25.

## Frozen contract

The tracked
[`quickdraw.bdq-epsilon-schedule.v1`](../../Research/trainer/bdq-epsilon-schedule-contract-v1.json)
contract has SHA-256
`0d0f3f855ecf19a642f5dab2e526a1be2d2f0a1a87dca70671f4fad3128c3fa7`
and binds R3H SHA-256
`53331db49c21d16c005ba6b1e7409a1cf40a1480d4f14d72d325700099bef581`.

The frozen stateless formula is:

```text
initial_epsilon
+ (final_epsilon - initial_epsilon)
  * clamp((completed_transition_count - replay_warmup_decisions)
          / decay_decisions, 0, 1)
```

Exact schedule values:

- counter: `BDQOptimizerController.decision_count`
- counter meaning: validated replay transitions already completed
- initial epsilon `1.0`
- final/training-floor epsilon `0.1`
- warmup `10000` transitions
- decay duration `100000` transitions
- decay starts at completed count `10000`
- midpoint count `60000`, epsilon `0.55`
- decay ends at completed count `110000`, epsilon `0.1`
- clamp before and after decay: enabled
- mutable schedule state: false
- exploratory-validation epsilon `0.05`
- final-evaluation epsilon `0.0`
- evaluation mutates training state: false

The scheduled selector uses exploration seed `61001`, branch-wise sampling,
a CPU `torch.Generator`, uniform sampling over ascending legal indices, and an
epsilon-`1.0` fast path that skips an unused network forward pass. It preserves
the existing fixed-selector behavior rather than altering R3E-R3H evidence.

## Validation and limits

All `30` focused R3I tests, all `107` trainer tests, and all `124` Python
research tests passed. Tests covered exact boundaries, statelessness, schema
drift, seeded repeatability, mask safety, the full-exploration fast path, and
invalid inputs.

R3I launched no Unity process and collected no live trace. It performed no
optimizer update or target synchronization and produced no trained weight,
checkpoint, export, held-out evaluation, or effectiveness evidence.

