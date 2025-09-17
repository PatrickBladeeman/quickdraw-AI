# quick-draw — TASKS (Execution Plan & Checklists)

This file is the **single source of truth for work items**. Codex and humans should follow it in order, checking acceptance criteria as they go. Keep edits **scoped to** `Assets/_Project/**` unless the task explicitly says otherwise.

> **Core success metric:** From `GUN_AIMED_AT_ME` event to **visible pose change** must be **p50 < 150 ms** and **p95 < 250 ms** on the development machine (Editor, VSync OFF, Incremental GC ON).

---

## 0) Ground rules (must not drift)
- Work only under `Assets/_Project/**` unless adding a package or a scene.
- Never put **file I/O, networking, or allocations** in the Reflex path.
- Use **Time.realtimeSinceStartup** for latency timestamps. (Not `Time.time`.)
- Keep **VSync = Don’t Sync**, **Incremental GC = ON**, **Enter Play Mode: Domain Reload OFF** for iteration.
- Use **public serialized fields** for tunables; prefer `ScriptableObject` if reused.
- Avoid LINQ, `foreach`, boxing, or `string` building in hot paths.

---

## 1) Scene: `Test_Arena.unity` (if not already present)

**Goal:** Minimal, consistent testbed.

### Steps
- Create `Assets/_Project/Scenes/Test_Arena.unity`.
- Blockout:
  - Floor: 12×12 (ProBuilder Plane or Cube).
  - Ceiling: 12×12 @ Y=3.0.
  - Walls: 4 thin boxes at room edges.
  - Columns: 2 cylinders inside the room.
- Create `Systems` (empty GO) and attach:
  - `DevOverlay` (shows FPS and realtime).
  - `JsonlLogger` (global logger, singleton).
- Create **Layer** `NPC` (Edit → Project Settings → Tags and Layers).
- Save scene.

### Acceptance
- Scene opens without errors; play mode shows an overlay (FPS + time).
- No pink materials (URP assigned or Built-in shaders OK).

---

## 2) Player: Minimal first-person controller

**Goal:** Movement & aim without external dependencies.

### Files
- `Assets/_Project/Code/Core/SimpleFPController.cs` (already provided; verify)
- Add **CharacterController** + child **Camera** (MainCamera) under `Player`.

### Steps
- Attach `SimpleFPController` to `Player`.
- Assign `cam` to child Camera.
- Project Settings → Player → **Active Input Handling = Both**.

### Acceptance
- In play mode: WASD moves, mouse looks, **RMB** narrows FOV (aim), Shift sprints, Space jumps (optional).

---

## 3) Threat raycast: aim → event

**Goal:** Holding **RMB** and placing crosshair on an NPC triggers a direct threat event.

### Files
- `Assets/_Project/Code/AI/Perception/ThreatRaycaster.cs`

### Steps
- Add `ThreatRaycaster` to **Main Camera**.
- Inspector:
  - `npcMask` = **NPC** layer.
  - `maxDistance` = 50.
  - `refireCooldown` = 0.5s.
- On hit, call `SoftFOVPerception.OnDirectThreatDetected()` on that NPC.

### Acceptance
- With an NPC in front, holding **RMB** immediately triggers the NPC’s reflex (once wired in §5).
- Noise-free: no log/GC spikes in the Game view (Profiler optional).

---

## 4) Perception: soft FOV → suspicion → turn-in-place

**Goal:** Peripheral detection builds suspicion (0.25–0.6 s) with LoS; NPC turns to face the player and then transitions to `Threatened`.

### Files
- `Assets/_Project/Code/AI/Perception/SoftFOVPerception.cs` (exists; refine)

### Inspector defaults
- `coreFOV = 90`, `peripheralFOV = 140`
- `suspectTime = 0.45s`, `decayRate = 0.8`
- `tickRateHz = 12`, `turnYawSpeed = 300 deg/s`
- Assign `eye` = NPC transform; `player` = Player Camera transform.

### Implementation details
- Tick at `1 / tickRateHz` (NOT every frame).
- Compute angle via dot; LoS check **only** when within peripheral band.
- Suspicion hysteresis: enter ≥0.5, exit ≤0.3.
- When suspicious and **not facing**, rotate root yaw toward player at `turnYawSpeed`. When |Δyaw|<3°, set `_facingThreat=true` and **call Reflex** (next task).

### Logging (JSONL)
- On first valid detect per suspicious episode, `{"t":"suspicion","npcId","ts","angleDeg","time_in_suspicious_ms"}`.

### Acceptance
- Player edges into the peripheral cone: NPC looks/hesitates, turns, then transitions to reflex.
- No stuttering at the cone boundary (hysteresis working).

---

## 5) Reflex: selector + “RaiseHands_High” (variant #1)

**Goal:** On `Threatened`, begin visible pose change **this frame**.

### Files
- `Assets/_Project/Code/AI/Reflex/ReflexSelector.cs`

### Variant: `RaiseHands_High`
- Params:
  - `hand_height` base 0.85 (+/− 0.08 jitter, clamp [0.7..0.95]).
  - `stepback_m` base 0.20 (+/− 0.05, clamp [0.05..0.60]).
- Behavior:
  - Optional tiny root translation backward (`stepback_m`).
  - Trigger Animator or Rig weight instantly (no await/StartCoroutine).
  - Gaze toward player’s **muzzle/face** (if LookAt rig present; placeholder OK).

### Latency logging
- Capture `t_event_received` before selection; set `t_anim_started = Time.realtimeSinceStartup` at the **same frame** you modify pose/weights.
- Emit `{"t":"reflex_latency","npcId","ts":t_anim_started,"lat_ms","variant","params":{...}}`.

### Acceptance
- 20–30 trials: **p50 < 150 ms**, **p95 < 250 ms** (computed in §7).
- No allocations or I/O on hot path (verify via Profiler “GC.Alloc” column = 0 during reflex).

---

## 6) NPC prefab & layer wiring

**Goal:** Reusable prefab with correct components.

### Steps
- Create `Assets/_Project/Prefabs/NPC/NPC_01.prefab` (or scene object initially).
- Components:
  - Collider (Capsule).
  - `SoftFOVPerception` (fields assigned).
  - `ReflexSelector`.
  - Optional `Animator` & Animation Rigging (LookAt/TwoBoneIK).
- **Layer**: set to `NPC`.

### Acceptance
- Dropping multiple NPCs works; each reacts independently with variation.

---

## 7) Summary & stats export on quit

**Goal:** On app quit, compute session p50/p95 and write a summary entry.

### Files
- `Assets/_Project/Code/Logging/JsonlLogger.cs` (extend)
- `Assets/_Project/Code/Logging/LatencySummary.cs` (new, optional helper)

### Steps
- Buffer `lat_ms` values in memory (e.g., `List<int> _latencies`).
- On `OnApplicationQuit`, compute:
  - `count`, `p50_ms`, `p95_ms` (sort + index or quick select).
- Append JSONL line:
  - `{"t":"summary","ts", "reflex":{"count":N,"p50_ms":X,"p95_ms":Y}}`.

### Acceptance
- After exit, log file contains a `summary` line with **count ≥ 20** and p50/p95 values.

---

## 8) Reaction variety (Week 2)

**Goal:** Add a second family and anti-clone mechanisms.

### Files
- `Assets/_Project/Code/AI/Reflex/ReflexSelector.cs` (extend)
- Optional: `Assets/_Project/ScriptableObjects/Reactions/*.asset`

### Variant #2: `Flinch_StepBack`
- Params:
  - `stepback_m` [0.1..0.6], `flinch_angle_deg` [−30..30] around player bearing.
- **No-repeat mask**: don’t pick the same variant twice within `cooldown_s`.
- **Style seed**: RNG seeded from NPC name hash so each NPC feels distinct.

### Acceptance
- Two NPCs side-by-side do **different** reactions and paramizations across repeated trials.

---

## 9) Tactical (Week 3 — scaffold only)

**Goal:** Skeleton that computes action weights and biases Reflex probabilities.

### Files
- `Assets/_Project/Code/AI/Tactical/TacticalController.cs` (new)

### Steps
- Implement simple utility scores: `Comply`, `Flee`, `Peek`, `SeekCover`.
- Expose `GetBias()` that returns a small struct of weights.
- ReflexSelector reads biases to adjust variant weights (no blocking).

### Acceptance
- Toggling inputs (distance/health/cover bool) shifts preferred variants.

---

## 10) LLM worker (Week 4 — optional, async only)

**Goal:** Off-thread bark pre-gen & tactical weight nudges.

### Approach
- Separate process (Node/Flask) with endpoints:
  - `/pre_barks?intent=plead&persona=scared` → `[string]`
  - `/nudge_weights?context=...` → `{delta_weights}`
- Unity side: background task polls during **idle** time; writes results to shared state (never blocks Reflex).

### Acceptance
- With LLM worker on/off, **Reflex latency distributions** are unchanged.

---

## 11) Ablation harness (Week 5)

**Goal:** Toggle features and auto-run scenarios.

### Flags
- `Ablation.BT_ONLY`, `+BARKS`, `+LLM_BIASES`, `+TTS`.

### Acceptance
- You can launch the same scene with different flags and produce comparable logs.

---

## 12) Plots & mini-study (Week 6–7)

**Goal:** Produce figures from JSONL and optional small user ratings.

### Steps
- Python notebook (outside Unity) to:
  - Plot latency histograms per variant.
  - Plot perceived responsiveness vs. latency budget (if you added enforced caps).
- Optional N=12–20 blinded video clips → ratings in Google Forms.

### Acceptance
- At least **3 plots** compiled into your paper.

---

## 13) Commit hygiene
- Commit scene & `.meta` files together.
- Keep `Library/` out of Git (check `.gitignore`).
- Use branches for Codex sessions: `codex/<task>`.

---
