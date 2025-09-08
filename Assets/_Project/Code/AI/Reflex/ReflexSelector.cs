using UnityEngine;
using QuickDraw.Logging;

namespace QuickDraw.AI.Reflex
{
    public class ReflexSelector : MonoBehaviour
    {
        [Header("Params")]
        [Range(0.7f, 0.95f)] public float handHeight = 0.85f;
        [Range(0.10f, 0.40f)] public float stepBackMeters = 0.20f;
        public Transform optionalLookTarget; // e.g., player's camera

        // Hooks (Animator or rig weights) - optional for scaffold
        public Animator animator;
        public string handsUpTrigger = "HandsUp";

        System.Random _rng;
        string _npcId;

        void Awake()
        {
            _npcId = gameObject.name;
            _rng = new System.Random(_npcId.GetHashCode());
        }

        public void OnThreatEvent(ThreatEventType evt, float tEventReceived)
        {
            if (evt != ThreatEventType.GUN_AIMED_AT_ME) return;

            // Param jitter (no artificial delay)
            float hh = Mathf.Clamp01(handHeight + RandRange(-0.08f, 0.08f));
            float sb = Mathf.Clamp(stepBackMeters + RandRange(-0.05f, 0.05f), 0.05f, 0.6f);

            // "Animation start" happens immediately here (no blocking / no LLM)
            float tAnimStart = Time.realtimeSinceStartup;

            // Optional: small step-back
            transform.position += -transform.forward * sb;

            // Optional: trigger animator
            if (animator && !string.IsNullOrEmpty(handsUpTrigger))
                animator.SetTrigger(handsUpTrigger);

            // Log latency + params
            JsonlLogger.Instance?.Log(new {
                t = "reflex_latency",
                npcId = _npcId,
                ts = tAnimStart,
                lat_ms = Mathf.RoundToInt((tAnimStart - tEventReceived) * 1000f),
                variant = "RaiseHands_High",
                @params = new { hand_height = hh, stepback_m = sb }
            });
        }

        float RandRange(float a, float b)
        {
            return (float)(_rng.NextDouble() * (b - a) + a);
        }
    }
}
