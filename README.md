# quick-draw

**Latency-bounded hybrid NPCs for real-time FPS interactions.**  
Goal: sub-150 ms median visible reaction when the player aims a gun at an NPC, while supporting longer-term tactical biasing and memory asynchronously.

> Engine: **Unity 6.0 LTS (URP)**

## Why this repo exists
This project demonstrates a **two-speed agent architecture**:
- **Reflex** (≤150 ms): non-blocking, deterministic reactions (e.g., flinch / hands-up / small step-back) with parametric variation.
- **Tactical** (100–400 ms): Utility/GOAP drives short-horizon choices (comply / flee / peek). 
- **LLM (async)**: Pre-generates bark lines, updates tactical weights and memory *between* spikes. Never blocks input.

## Week-1 Targets (MVP)
- Aim at NPC → **visible pose change** (hands-up or flinch) with **median <150 ms**, **p95 <250 ms**.
- **Soft FOV**: Peripheral detection builds suspicion; NPC turns to face before reflex.
- **Logging**: JSONL with timestamps for events, reaction params, and latencies. Summary p50/p95 on quit.

## Unity setup
- Version: **6.0 LTS** (6000.0.x)
- Template: **URP**
- Packages: Input System, ProBuilder, Animation Rigging, Newtonsoft JSON
- Recommended editor settings: Incremental GC ON; Enter Play Mode Options → enable (Domain Reload OFF, Scene Reload ON).

## Project layout
```
Assets/_Project/
  Code/
    Core/                # bootstrap & overlays
    AI/
      Reflex/            # reflex selector + reaction variants
      Perception/        # soft FOV + suspicion/turn-in-place
    Logging/             # JSONL logger + summary
  Prefabs/
  Scenes/
  ScriptableObjects/
    Reactions/
  Audio/
```

## Build/run
1. Open the project in Unity 6.0 LTS (URP).
2. Open scene: `Assets/_Project/Scenes/Test_Arena.unity` (create if missing).
3. Play. Hold **Right Mouse** to aim; look at the NPC. Reaction should be immediate.
4. Logs are written to `{persistentDataPath}/YYYYMMDD_session.jsonl` (buffered; summary on quit).

## Data logged (JSONL)
Example:
```json
{"t":"session_start","ts":123.45}
{"t":"threat_event","npcId":"NPC_01","ts":130.12,"angleDeg":35.4}
{"t":"reflex_latency","npcId":"NPC_01","ts":130.14,"lat_ms":92,"variant":"RaiseHands_High","params":{"hand_height":0.83,"stepback_m":0.22}}
{"t":"suspicion","npcId":"NPC_01","ts":129.90,"angleDeg":120.1,"time_in_suspicious_ms":410}
```

## Environment & secrets
Create `.env` from `.env.example` if/when you add cloud APIs (LLM, TTS). Never commit real keys.

## Licensing
Code: MIT (see LICENSE).  
**Assets:** Do not include paid/proprietary assets in the public repo. See `ASSETS_LICENSE.md`.

## Citation
If you use or reference this project, please cite via the `CITATION.cff`. A DOI can be minted by archiving a release on Zenodo.

## Roadmap (high-level)
- Week 1: Reflex + logging + soft FOV (this repo scaffold)
- Week 2: Add 2nd/3rd reaction family + Tactical (Utility/GOAP)
- Week 3: Async LLM worker for bark pre-gen & weight nudging
- Week 4+: Ablations, plots, short user study, paper write-up
