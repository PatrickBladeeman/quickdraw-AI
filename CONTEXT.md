Here’s a drop-in **`CONTEXT.md`** you can put at the repo root for Codex CLI. It’s exhaustive and opinionated, so Codex (and you) always have the same ground truth.

---

# quick-draw — Context & Requirements

> **Mission:** Build an FPS demo that **proves** latency-bounded, human-time NPC reactions (<150 ms median, <250 ms p95 visible change) while still enabling longer-horizon tactics and evolving behavior **without** blocking on LLMs.

This file is the single source of truth for Codex and contributors. Everything in here takes precedence over comments scattered in code.

---

## 0) One-paragraph summary

`quick-draw` is a Unity 6.0 LTS (URP or Built-in) project demonstrating a **two-speed agent**: an **instant Reflex layer** (animation/IK + param noise, no LLM), a slightly slower **Tactical layer** (Utility/GOAP), and an **async LLM worker** (pre-generates bark lines, updates bias/memory *between* spikes). The core research claim is that **sub-150 ms median** visible NPC reactions at gunpoint are achievable **with variety** and **without** putting LLM inference on the input thread. The repo includes full instrumentation (JSONL logs, p50/p95 summaries, ablation toggles) and a tiny arena scene.

---

## 1) Why this exists (background & goals)

* **Problem:** Generative NPCs feel smart in downtime but break in combat because LLM latency (300–1000 ms) is too slow for FPS loops (16–33 ms per frame).
* **Hypothesis:** Split control into **Reflex (ms)** vs. **Deliberation (100–1000 ms)**. Keep the Reflex path purely deterministic & parametric; let LLMs steer trends asynchronously.
* **Success criteria (hard):**

  * Visible pose change after gunpoint event: **median <150 ms**, **p95 <250 ms** (logged from event→anim start).
  * Reaction **variety** (param noise, micro-timing, gaze IK, no-repeat masks) so two NPCs don’t look like clones.
  * **LLM calls** limited to event-driven, off-thread tasks (bark pre-gen, bias updates); **never** in Reflex loop.
  * Ablations & plots that **show the trade-offs** (responsiveness ↔ perceived credibility ↔ cost).

---

## 2) Architecture (must not drift)

### 2.1 Layers & responsibilities

* **Reflex (≤150 ms; Update tick)**

  * Inputs: high-salience events (`GUN_AIMED_AT_ME`, `NEAR_MISS`, `WOUNDED`, etc.).
  * Output: start animation/rig changes **this frame**; apply param noise and micro-motions; log timestamps.
  * No I/O, no allocations, no async waits. **Purely local state.**

* **Tactical (100–400 ms; Utility/GOAP/State machine)**

  * Decides **comply / flee / peek / seek cover / trade**; writes **weights** the Reflex selector reads.
  * Reads world state (cover, distance, health) + slow LLM biases; never blocks Reflex.

* **LLM Worker (async; 400–1500 ms when used)**

  * Runs off-thread / off-process (HTTP).
  * Pre-generates **bark variants** per semantic tag/personality (e.g., `plead+panicked`, `stall+calm`).
  * Updates **tactical bias weights** & **memory** after encounters.
  * **Never** directly triggers animations or blocks gameplay.

### 2.2 Data flow (high level)

```
Player Aim (RMB) → ThreatRaycaster (Camera) → OnDirectThreatDetected() → SoftFOV/Perception (NPC)
→ if core-FOV or suspicion reached → state: Threatened
→ ReflexSelector.SelectAndPlay(variant, params)  [<150 ms]
   ↳ anim rig weights, step-back, gaze target, nonverbal SFX
   ↳ logs: t_event_received, t_anim_started, lat_ms, variant, params

Meanwhile:
Tactical weights influence ReflexSelector probabilities (no blocking).
LLM worker (idle time): pre-gen barks, nudge weights, write memory.
```

---

## 3) Tech stack & project settings

* **Unity:** 6.0 LTS (6000.0.xx).
  **Render Pipeline:** URP preferred; Built-in acceptable for Week 1.
* **Packages:** Input System (later), ProBuilder, Animation Rigging, Newtonsoft JSON; (optional) Cinemachine.
* **Editor/Project settings:**

  * **Quality → VSync:** **Don’t Sync** (avoid 16.7 ms quantization).
  * **Player → Other:** **Incremental GC** = ON.
  * **Editor → Enter Play Mode Options:** Enable; **Domain Reload OFF**, **Scene Reload ON**.
  * **Player → Active Input Handling:** **Both** (legacy axes + new Input System).

---

## 4) Scene, prefabs, layers

* **Scene:** `Assets/_Project/Scenes/Test_Arena.unity`
  Grey room (12×12), four walls, 2 columns. Keep it simple to avoid perf noise.
* **Layers:** create **NPC** layer; NPC colliders go here. ThreatRaycaster’s `npcMask` includes this layer.
* **GameObjects:**

  * **Systems**: `DevOverlay`, `JsonlLogger` (one per scene).
  * **Player**: `SimpleFPController` (CharacterController + child Camera tagged MainCamera).
  * **NPC\_XX**: Collider + `ReflexSelector` + `SoftFOVPerception` (+ Animator later).

---

## 5) Components (code contracts & behavior)

> File paths assume `Assets/_Project/Code/...`

### 5.1 `SimpleFPController.cs` (Core/)

* Move with WASD, mouse look; **RMB** narrows FOV (aim), reduces sensitivity; optional Jump.
* Public fields (defaults):

  * `moveSpeed=5`, `sprintMultiplier=1.4`, `mouseSensitivity=1.8`, `mouseSensitivityAim=1.2`,
  * `normalFOV=70`, `aimFOV=55`, `fovLerp=12`, `gravity=-9.81`, `jumpHeight=1.1`.

### 5.2 `ThreatRaycaster.cs` (AI/Perception/)

* Lives on the **Main Camera**.
* When **RMB** down, raycast from viewport center to `maxDistance` (default 50 m) against `npcMask`.
* On hit: call `SoftFOVPerception.OnDirectThreatDetected()` on that NPC.
* Debounce per-NPC via `refireCooldown` (default 0.5 s).
* **No logging** here; Perception/Reflex will log.

### 5.3 `SoftFOVPerception.cs` (AI/Perception/)

* Inputs: `eye` (Transform), `player` (Transform), `occludersMask`.
* Params:

  * **Angles:** `coreFOV=90°`, `peripheralFOV=140°`
  * **Suspicion:** `suspectTime=0.45s`, `decayRate=0.8`, `tickRateHz=12`, `turnYawSpeed=300°/s`
* Logic:

  * At `tickRateHz`, compute angle to player; if **within core** and LoS → **immediate** Threatened.
  * If **within peripheral** and LoS → build `_suspicion` over `suspectTime` (hysteresis enter≥0.5/exit≤0.3).
  * When suspicious and **not facing**, rotate yaw towards player at `turnYawSpeed`.
  * When facing (|Δyaw|<3°) → **Threatened** → invoke Reflex:
    `reflex.OnThreatEvent(GUN_AIMED_AT_ME, Time.realtimeSinceStartup)`.
* Logs (JSONL via `JsonlLogger`):

  * `suspicion`: `npcId`, `ts`, `angleDeg`, `time_in_suspicious_ms` (approximate).

### 5.4 `ReflexSelector.cs` (AI/Reflex/)

* Public fields:

  * Animator (optional), `handsUpTrigger` string (optional).
  * Base params & jitter bounds:

    * `handHeight` base 0.85 (range ±0.08),
    * `stepBackMeters` base 0.20 (clamped 0.05–0.6),
    * Per-NPC **style seed** from name hash for deterministic RNG.
* Main method:

  * `OnThreatEvent(ThreatEventType.GUN_AIMED_AT_ME, float tEventReceived)`.
  * Picks a **reaction variant** (start with `RaiseHands_High`, later add more).
  * Applies **immediately**:

    * adjust rig/anim weights this frame,
    * apply optional small root translation (step-back),
    * set gaze/look target to muzzle/face (IK),
    * (audio to come later).
  * Logs: `reflex_latency` with `npcId`, `ts=t_anim_started`, `lat_ms`, `variant`, `params`.

#### 5.4.1 Reaction families (to implement this sprint)

* `RaiseHands_High`: params `hand_height`, `stepback_m`, `latency_jitter` (no extra delay, just for logging).
* `Flinch_StepBack`: params `stepback_m` (0.1–0.6), `flinch_angle` (±30° around player bearing).
* (later) `Freeze_Shiver`, `Crouch_Peek`, `Drop_Weapon` (only if time permits).

#### 5.4.2 Variety mechanisms

* **Param noise**: hand height ±8%, step-back ±0.05 m, flinch angle ±30°, tiny latency telemetry jitter for realism (do **not** add real delay).
* **Micro-timing**: sample reaction start jitter only for logging; do not delay animation start.
* **No-repeat mask**: prevent the same variant from firing twice in a short window per NPC.
* **Per-NPC style seed**: seed RNG so two NPCs differ consistently.

---

## 6) Logging & metrics (non-negotiable)

### 6.1 Logger

* `JsonlLogger` buffers to memory; flushes on quit (add periodic flush later if needed).
* Output path: `Application.persistentDataPath/YYYYMMDD_session.jsonl`.

### 6.2 Event types (examples)

```json
{"t":"session_start","ts":123.456,"unity":"6000.0.57f1"}
{"t":"scene_loaded","ts":124.001,"name":"Test_Arena"}
{"t":"threat_event","ts":200.120,"npcId":"NPC_01","source":"raycast","distance_m":6.2}
{"t":"suspicion","ts":200.200,"npcId":"NPC_01","angleDeg":128.5,"time_in_suspicious_ms":410}
{"t":"reflex_latency","ts":200.230,"npcId":"NPC_01","lat_ms":92,"variant":"RaiseHands_High","params":{"hand_height":0.83,"stepback_m":0.22}}
{"t":"summary","ts":999.999,"reflex":{"count":30,"p50_ms":112,"p95_ms":208}}
```

### 6.3 Latency measurement points

* `t_event_received`: immediately before selection (from Perception or direct threat).
* `t_anim_started`: same frame we set anim/rig weights or move root → **visible change**.
* **Latency (ms) = (`t_anim_started - t_event_received`) × 1000**.

### 6.4 Summaries / plots

* At app quit (or on demand), compute session **p50** and **p95** for `reflex_latency`.
* Later: Python notebook to plot histograms by variant; angle-vs-hesitation scatter.

---

## 7) Tactical & LLM (Weeks 2–4 planning)

### 7.1 Tactical (Utility AI or GOAP)

* Goals: `Comply`, `Flee`, `Peek`, `SeekCover`, `Trade`.
* Utilities consider: `health`, `distance_to_player`, `cover_available`, `recent_memory` (from LLM), `fearfulness`.
* Tactical outputs **weights** (`w_compliance`, `w_flee`, …) that **bias** variant probabilities in ReflexSelector.

### 7.2 LLM Worker (async service)

* A background process (Node/Flask) with endpoints:

  * `/pre_barks?intent=plead&persona=scared` → returns 10 short lines.
  * `/nudge_weights?context=...` → returns small deltas for Tactical bias.
* Update cadence: on scene load and during quiet periods.
* Store bark banks and biases in ScriptableObjects or in-memory lists. **Never** block Reflex or Tactical.

### 7.3 Audio (fast path)

* On Reflex start: play **nonverbal stinger** (gasp/whimper) **immediately**.
* If streaming TTS is available, start speech when phonemes arrive; else show quick subtitle from bark bank.

---

## 8) Soft FOV — exact behavior

* Two cones: **coreFOV=90°** (instant) and **peripheralFOV=140°**.
* Suspicion builds only with **LoS**. Build time ≈ **0.25–0.6 s** (param `suspectTime`).
* **Hysteresis**: enter Suspicious ≥0.5; leave ≤0.3.
* **TurnInPlace**: when suspicious and not facing, rotate yaw at **300°/s** until facing player (|Δyaw|<3°). Then **Threatened** → Reflex.
* Logs: `angleDeg`, `time_in_suspicious_ms` (approx), `time_to_face_player` (optional).

---

## 9) Performance budgets & hygiene

* **Reflex path**: zero allocations; no file I/O; no network calls.
* **Perception tick**: 10–20 Hz, one Linecast only when within peripheral band.
* **Animation**: use Animation Rigging for head/hand IK; keep clips minimal.
* **Project:** keep `VSync=Don’t Sync`; use Incremental GC; Enter Play Mode without domain reload (toggle back only if debugging breakpoints misbehave).

---

## 10) Repository layout (already created)

```
Assets/_Project/
  Code/
    Core/                # overlays, simple controller
    AI/
      Reflex/            # reflex selector + variants
      Perception/        # soft FOV + raycaster
    Logging/             # JSONL logger
  Prefabs/
  Scenes/
  ScriptableObjects/Reactions/
  Audio/
.github/workflows/
README.md
CITATION.cff
ASSETS_LICENSE.md
.env.example
```

---

## 11) Week-by-week plan (2 months)

### Week 1 — **Reflex MVP + Logs + Soft FOV**

* ✅ Scene, Player, NPC prefab, ThreatRaycaster, SoftFOVPerception, ReflexSelector.
* ✅ JSONL logger, summary p50/p95 on quit.
* ✅ SLA met: median <150 ms, p95 <250 ms on “gun aimed”.

### Week 2 — **Variety & Second Reaction**

* Add `Flinch_StepBack` variant; param noise; no-repeat mask; per-NPC style seed.
* Begin a small Python notebook for latency histograms.

### Week 3 — **Tactical Layer**

* Utility/GOAP with `Comply/Flee/Peek/SeekCover` (lightweight, no pathfinding drama).
* Tactical outputs **weight biases** read by ReflexSelector.

### Week 4 — **LLM Worker (Async) & Barks**

* Background service that pre-generates bark lines per tag/persona.
* Nonverbal stinger now + streaming TTS or subtitle (optional).
* Add metrics: LLM call count, token cost (if applicable).

### Week 5 — **Ablation harness & Auto-runner**

* Config flags: `BT_ONLY`, `+BARKS`, `+LLM_BIASES`, `+TTS`.
* Auto-runner captures fixed scenarios + logs + short MP4s.

### Week 6 — **Main experiments**

* Latency budget sweep (100/150/250 ms enforced caps for Reflex start, if you add one).
* Optional user mini-study (N≈12–20) on perceived responsiveness/credibility from blinded clips.

### Week 7 — **Docs & Plots**

* Tech report (4–6 pp): Abstract, Problem, Method, Instrumentation, Results, Ablations, Limits.
* Plots: reaction time distro; credibility vs. latency budget; cost vs. quality.
* Project page + video.

### Week 8 — **Polish, feedback, release**

* Address feedback; tag release; mint DOI.

---

## 12) Acceptance criteria (Definition of Done)

* **Logs prove**: median `<150 ms` and p95 `<250 ms` from `GUN_AIMED_AT_ME` → animation start.
* **Reflex variety**: at least 2 reaction families with param noise; visible differences across two NPCs standing side-by-side.
* **No blocking**: LLM used only for pre-gen and biases; Reflex latency unchanged with/without LLM worker.
* **Ablations** implemented; one notebook or dashboard with plots.

---

## 13) Coding standards & guardrails

* **No** physics or perception in `Update` every frame unless necessary; Perception ticks at 10–20 Hz with early outs.
* **No** allocations in Reflex path (`new`/LINQ/boxing).
* **All file I/O off main thread** (logger buffers; flush on quit or timer).
* **Public fields** for tunables (so designers/future you can tweak in Inspector).
* **Layer masks** are serialized; avoid `LayerMask.GetMask` in hot code.

---

## 14) .codexignore (keep Codex focused)

Create `.codexignore` at repo root:

```
Library/
Temp/
Logs/
Obj/
Build*/
UserSettings/
MemoryCaptures/
*.unitypackage
*.png
*.jpg
*.tga
*.exr
*.psd
*.fbx
*.anim
*.mp4
*.wav
*.mp3
```

---

## 15) Open tasks (Week 1)

* [ ] Create/Test scene `Test_Arena.unity`: floor, ceiling, 4 walls, 2 columns.
* [ ] Add `Systems` GO with `DevOverlay` + `JsonlLogger`.
* [ ] Player rig: `SimpleFPController` (CharacterController + Camera).
* [ ] NPC: Capsule on `NPC` layer + `ReflexSelector` + `SoftFOVPerception` (wire `player`/`eye`).
* [ ] `ThreatRaycaster` on Main Camera (RMB aim → direct threat).
* [ ] Log `reflex_latency` entries with `lat_ms`; dump p50/p95 on quit.
* [ ] Verify SLA with 20–30 trials; commit.

---

## 16) Future (nice-to-have only after DoD)

* Head/eye saccade jitter & breath SFX on Reflex start.
* Environment-aware variation (e.g., toss weapon left if table is left).
* TTS streaming fallback → subtitle if latency exceeds threshold.
* Tiny gating heuristic (call LLM only when uncertainty high) — **not required**.

---

## 17) Risks & fallbacks

* **Starter Assets friction:** we avoid them; use our own controller.
* **URP pink materials:** run Render Pipeline Converter or use Built-in RP for Week 1.
* **Audio latency:** hide with instant nonverbal stinger; speech later.
* **Scope creep (inventory/crafting):** explicitly **out of scope** for this research MVP.

---

## 18) Example reaction template (reference)

```json
{
  "event": "GUN_AIMED_AT_ME",
  "variants": [
    {
      "name": "RaiseHands_High",
      "weight": 0.35,
      "params": {
        "hand_height": [0.70, 0.95],
        "stepback_m": [0.10, 0.40]
      },
      "cooldown_s": 2.0
    },
    {
      "name": "Flinch_StepBack",
      "weight": 0.35,
      "params": {
        "stepback_m": [0.10, 0.60],
        "flinch_angle_deg": [-30, 30]
      },
      "cooldown_s": 1.5
    },
    { "name": "Freeze_Shiver", "weight": 0.20, "params": {}, "cooldown_s": 1.0 },
    { "name": "Crouch_Peek",   "weight": 0.10, "params": {}, "cooldown_s": 2.5 }
  ]
}
```

Implementation can remain in C#; this JSON is conceptual. Tactical layer nudges `weight`s; LLM edits weights **only** between spikes.

---

## 19) Commands & quicklinks

* **Build/Run:** in-Editor for Week 1; Windows IL2CPP module optional later.
* **Logs path (Windows Editor):**
  `C:\Users\<you>\AppData\LocalLow\<CompanyName>\<ProductName>\YYYYMMDD_session.jsonl`
* **Git hygiene:** `.gitignore` excludes `Library/` etc. Use `git lfs` if you add binaries later.

---

**End of CONTEXT.md** — if Codex needs more detail, add it here so the whole toolchain stays aligned.
