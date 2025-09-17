```markdown
# quick-draw — Architecture & Code Contracts

This doc explains **how the system fits together**, with module boundaries, exact interfaces, and state machines. It is the authoritative reference for Codex and contributors.

---

## 0) High-level picture

**Two-speed agent:**
- **Reflex (≤150 ms):** deterministic, parametric reactions; never blocks.
- **Tactical (100–400 ms):** short-horizon choice weighting (comply/flee/peek/seek cover).
- **LLM (async):** pre-writes barks and nudges tactical weights; **never** in the input thread.

```

Player (RMB Aim)
│
├─ Camera.Ray → ThreatRaycaster ───► NPC.SoftFOVPerception.OnDirectThreatDetected()
│                                            │
│                                            ├─ Core FOV: Threatened immediately
│                                            └─ Peripheral: suspicion→turn→Threatened
│
└────────────────────────────────────────────────► NPC.ReflexSelector.SelectAndPlay()
│
├─ Anim/Rig weights THIS FRAME
├─ Optional step-back, gaze
└─ Log reflex\_latency (t\_event→t\_anim\_start)

````

---

## 1) Modules & namespaces

- `QuickDraw.Core` — overlays, simple controller, utilities.
- `QuickDraw.Logging` — JSONL logger & summaries.
- `QuickDraw.AI.Perception` — Soft FOV, raycaster.
- `QuickDraw.AI.Reflex` — reflex selector & variants.
- `QuickDraw.AI.Tactical` — (week 3) utility/GOAP; provides bias weights.

> Consider adding an **asmdef** per module later (`Assets/_Project/Code/<Module>/<Module>.asmdef`) to speed compile times and enforce dependencies.

---

## 2) Component contracts

### 2.1 `DevOverlay` (Core)
- **Purpose:** show FPS & realtime to visually monitor perf budget.
- **Public fields:** none (style optional).
- **Notes:** runs in `OnGUI()` to keep it trivial.

### 2.2 `SimpleFPController` (Core)
- **Purpose:** minimal FP movement + aim FOV.
- **Public fields:** `cam`, `moveSpeed`, `sprintMultiplier`, `mouseSensitivity`, `mouseSensitivityAim`, `normalFOV`, `aimFOV`, `fovLerp`, `jumpHeight`, `gravity`.
- **Notes:** Uses legacy `Input` so Active Input Handling must be **Both**.

### 2.3 `ThreatRaycaster` (Perception)
- **Purpose:** convert aim (RMB + crosshair on NPC) → direct threat event.
- **Public fields:** `cam`, `npcMask`, `maxDistance=50f`, `refireCooldown=0.5f`.
- **Behavior:** While RMB held, raycast from `cam.ViewportPointToRay(0.5,0.5)` to `maxDistance` with `npcMask`. On hit, find nearest `SoftFOVPerception` up the hierarchy and call `OnDirectThreatDetected()`. Debounce per NPC.
- **Performance:** ≤ 1 raycast per frame while aiming; negligible.

### 2.4 `SoftFOVPerception` (Perception)
- **Purpose:** perception with soft peripheral band and hesitation; signal Threatened when facing.
- **Public fields:**
  - Refs: `eye:Transform`, `player:Transform`, `occludersMask:LayerMask`
  - Angles: `coreFOV=90`, `peripheralFOV=140`
  - Suspicion: `suspectTime=0.45`, `decayRate=0.8`
  - Tick: `tickRateHz=12`
  - Turn: `turnYawSpeed=300`
  - Hooks: `reflex:ReflexSelector`, `animator:Animator (optional)`
- **State machine:**
  - `Idle` → `Suspicious` (when within peripheral + LoS; build suspicion with hysteresis).
  - `TurnInPlace` (implicit: while Suspicious and not facing): rotate yaw until |Δyaw|<3°.
  - `Threatened`: call `reflex.OnThreatEvent(GUN_AIMED_AT_ME, now)`.
  - `Idle` (decay) when player moves away/out of LoS and suspicion < 0.3.
- **Logging:** `suspicion` with `angleDeg` and `time_in_suspicious_ms`.

**Pseudocode (tick):**
```csharp
TickPerception():
  toPlayer = (player - eye).normalized
  angleDeg = acos(dot(fwd, toPlayer)) * Rad2Deg
  withinPeriph = angleDeg <= peripheralFOV
  withinCore   = angleDeg <= coreFOV
  hasLoS = withinPeriph && !Physics.Linecast(eye, player, occludersMask)

  if (withinCore && hasLoS):
      suspicion = 1
  else if (withinPeriph && hasLoS):
      suspicion = clamp01(suspicion + dt / suspectTime)
  else:
      suspicion = clamp01(suspicion - decayRate * dt)

  if (suspicion >= 0.5):
      // turn toward player
      targetYaw = yaw(lookRotation(toPlayer))
      currentYaw = yaw(transform.rotation)
      newYaw = moveTowardsAngle(currentYaw, targetYaw, turnYawSpeed * Time.deltaTime)
      transform.rotation = yaw(newYaw)
      if (abs(deltaAngle(newYaw, targetYaw)) < 3):
          reflex.OnThreatEvent(GUN_AIMED_AT_ME, Time.realtimeSinceStartup)
````

### 2.5 `ReflexSelector` (Reflex)

* **Purpose:** choose a reaction variant and start visible pose change immediately.
* **Public fields:** `Animator animator`, `string handsUpTrigger="HandsUp"`, base params for variants, jitter ranges.
* **Methods:**

  * `OnThreatEvent(ThreatEventType evt, float tEventReceived)`
* **Variants (initial):**

  * `RaiseHands_High` — primary: hands up, small step-back, gaze to player.
  * (Week 2) `Flinch_StepBack` — flinch angle ±30°, bigger step-back.
* **Variety mechanisms:**

  * Param noise; no-repeat masks; per-NPC seeded RNG.
* **Logging:** `reflex_latency` with `lat_ms`, `variant`, `params`.

**Pseudocode (core):**

```csharp
OnThreatEvent(evt, tEvent):
  if (evt != GUN_AIMED_AT_ME) return
  // sample params (no waits)
  hh = clamp01(baseHandHeight + rand(-0.08, 0.08))
  sb = clamp(baseStepBack + rand(-0.05, 0.05), 0.05, 0.60)

  // start pose THIS FRAME
  tStart = Time.realtimeSinceStartup
  transform.position += -transform.forward * sb
  if (animator) animator.SetTrigger(handsUpTrigger)

  Logger.Log({
    t: "reflex_latency", npcId, ts: tStart,
    lat_ms: int((tStart - tEvent) * 1000),
    variant: "RaiseHands_High",
    params: { hand_height: hh, stepback_m: sb }
  })
```

### 2.6 `JsonlLogger` (Logging)

* **Purpose:** buffered JSONL writes; zero hitches during play.
* **Behavior:** `Log(object)` → serialize (JsonUtility/Newtonsoft) → append to in-memory buffer; flush on quit (add periodic flush if needed).
* **Summary:** on quit, compute p50/p95 from collected `lat_ms` list; log a `summary` line.

**Percentile helper:**

```csharp
static int Percentile(List<int> xs, float p){
  if (xs.Count == 0) return 0;
  xs.Sort();
  float idx = (xs.Count - 1) * p;
  int lo = (int)Mathf.Floor(idx);
  int hi = (int)Mathf.Ceil(idx);
  if (lo == hi) return xs[lo];
  return Mathf.RoundToInt(Mathf.Lerp(xs[lo], xs[hi], idx - lo));
}
```

---

## 3) Data contracts (events & logs)

### Event Types

* `session_start`: `{ t, ts, unity }`
* `scene_loaded`: `{ t, ts, name }`
* `threat_event`: `{ t, ts, npcId, source("raycast"|"perception"), distance_m }` *(optional)*
* `suspicion`: `{ t, ts, npcId, angleDeg, time_in_suspicious_ms }`
* `reflex_latency`: `{ t, ts, npcId, lat_ms, variant, params{...} }`
* `summary`: `{ t, ts, reflex{ count, p50_ms, p95_ms } }`

### Keys

* `ts`: `Time.realtimeSinceStartup` (float seconds).
* `lat_ms`: integer milliseconds (rounded).
* `npcId`: `gameObject.name` (stable across sessions if prefab named).

---

## 4) State machines

### Perception (soft FOV)

```
+-------+               +-------------+               +-------------+
| Idle  | -- peripheral -> Suspicious  -- facing -->   Threatened   -> (signal Reflex)
+-------+               +-------------+               +-------------+
    ^                        |   ^
    |   (decay < 0.3)       |   | (angle out of bands or LoS lost)
    +------------------------+---+
```

* Enter Suspicious when `(angle <= peripheralFOV && LoS)` and build suspicion to ≥ 0.5 over `suspectTime`.
* Leave Suspicious when suspicion ≤ 0.3 (hysteresis) or LoS/angle invalid.
* During Suspicious, rotate toward player; when |Δyaw|<3°, trigger Threatened.

### Reflex (selector)

```
Threatened
  └─> SampleVariant (weights + tactical bias, no- repeat)
        └─> ApplyPose (THIS FRAME: rig weights, step-back)
              └─> LogLatency (t_event → t_start)
```

---

## 5) Performance budgets

* Reflex path (selection + pose start): **≤ 1 ms** on target machine.
* Perception tick: **≤ 0.2 ms** @ 12–20 Hz (1 LoS cast at most).
* No **GC.Alloc** during Reflex (Profiler should show 0 B/frame).
* Rendering not a focus; URP/Built-in acceptable.

---

## 6) Animation & rigging notes

* Use **Animation Rigging** for LookAt (head) and TwoBoneIK (hands).
* If you don’t have clips yet:

  * Hands-up can be achieved with rig weights + constraints.
  * Step-back is a small root translation; keep it small to avoid collider tunneling (CharacterController on NPC not required—static transform is fine for MVP).
* Blend curves should be snappy (≤ 0.1 s) to maintain visible immediacy.

---

## 7) Tactical & LLM integration (future)

### TacticalController (Week 3)

* Inputs: `health`, `distance_to_player`, `cover_available`, `recent_memory`.
* Output: `BiasWeights { comply, flee, peek, seekCover }` in \[0..1].
* ReflexSelector reads these biases to slightly adjust variant probabilities.

### LLM Worker (Week 4)

* **Never** called from Reflex or Perception.
* Runs in background:

  * Pre-gen barks per tag/persona and store in local lists.
  * Nudge tactical biases (e.g., slightly increase “comply” after being spared).
* Fail open: if worker is down, gameplay is identical; only barks might fall back to canned lines.

---

## 8) Editor settings (for reproducibility)

* Project Settings:

  * **Quality → VSync:** **Don’t Sync**
  * **Player → Other:** **Incremental GC ON**
  * **Editor → Enter Play Mode:** **Enable**, **Domain Reload OFF**, **Scene Reload ON**
* Asset Pipeline:

  * **Auto Refresh** ON (otherwise manually Assets → Refresh after Codex edits).

---

## 9) Testing & verification

### Manual functional tests

* **Direct raycast:** Stand in front, hold RMB → immediate hands-up; release RMB and re-aim after cooldown → repeats.
* **Peripheral:** Approach from behind/outside peripheral → no reaction; slide into peripheral → short hesitation → turn → hands-up.
* **Multi-NPC:** Place two NPCs; repeated trials show different variants/params (once variant #2 is added).

### Latency measurement

* Perform 30 trials in Editor with Game window focused.
* Inspect JSONL:

  * Count of `reflex_latency` ≥ 30.
  * `summary.reflex.p50_ms < 150`, `p95_ms < 250`.

---

## 10) Non-goals (out of scope for MVP)

* Inventory/crafting/carry weight.
* Group tactics, comms, squad orders.
* Pathfinding beyond simple step-back/crouch.
* Live LLM calls in Reflex/Tactical hot paths.

---

## 11) File map (initial)

```
Assets/_Project/
  Code/
    Core/
      DevOverlay.cs
      SimpleFPController.cs
    Logging/
      JsonlLogger.cs
      LatencySummary.cs       (optional helper)
    AI/
      Perception/
        SoftFOVPerception.cs
        ThreatRaycaster.cs
      Reflex/
        ReflexSelector.cs
        ThreatEvents.cs
    Tactical/                 (week 3)
  Prefabs/
    NPC/
      NPC_01.prefab           (if you prefab it)
  Scenes/
    Test_Arena.unity
  ScriptableObjects/
    Reactions/                (optional later)
  Audio/                      (nonverbal stingers later)
```

---

## 12) Coding standards

* Namespace per module (`QuickDraw.Core`, `QuickDraw.AI.Reflex`…).
* `[DisallowMultipleComponent]` where appropriate.
* Guard null refs in `Awake()`; serialize all tunables.
* Use `readonly` fields where possible; avoid `public static` except for singletons like Logger.
* Avoid coroutines in Reflex; use direct method calls.

---

## 13) Risks & mitigations

* **Editor stutter:** Keep logger buffered; no file writes per frame.
* **Breakpoint weirdness:** If breakpoints don’t hit (Domain Reload OFF), temporarily re-enable domain reload to debug, then switch back.
* **Raycast spam:** Only raycast while aiming; debounce hits with `refireCooldown`.

---

*End ARCH.md.*

```
::contentReference[oaicite:0]{index=0}
```
