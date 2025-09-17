using UnityEngine;
using QuickDraw.Logging;

namespace QuickDraw.AI.Perception
{
    public class SoftFOVPerception : MonoBehaviour
    {
        [Header("References")]
        public Transform eye;           // where we cast/check from
        public Transform player;        // player camera/root
        public LayerMask occludersMask; // for line of sight

        [Header("Angles (deg)")]
        [Range(10, 170)] public float coreFOV = 90f;
        [Range(10, 179)] public float peripheralFOV = 140f;

        [Header("Suspicion")]
        [Range(0.1f, 1.0f)] public float suspectTime = 0.45f; // seconds to trigger from periphery
        [Range(0.0f, 2.0f)] public float decayRate = 0.8f;
        [Range(2f, 20f)] public float tickRateHz = 12f;
        public float turnYawSpeed = 300f; // deg/sec

        [Header("Hooks")]
        public QuickDraw.AI.Reflex.ReflexSelector reflex;
        public Animator animator; // optional, e.g., to blend head look

        float _suspicion; // [0,1]
        float _nextTick;
        bool  _facingThreat;
        string _npcId;

        void Awake()
        {
            if (eye == null) eye = transform;
            _npcId = gameObject.name;
        }

        void Update()
        {
            if (Time.time >= _nextTick)
            {
                _nextTick = Time.time + 1f / Mathf.Max(1f, tickRateHz);
                TickPerception();
            }

            // If suspicious and not yet facing player, begin turn-in-place
            if (_suspicion >= 0.5f && !_facingThreat)
            {
                Vector3 toPlayer = (player.position - transform.position);
                Vector3 fwd = transform.forward;
                toPlayer.y = 0f; fwd.y = 0f;

                if (toPlayer.sqrMagnitude > 0.001f)
                {
                    float targetYaw = Quaternion.LookRotation(toPlayer.normalized, Vector3.up).eulerAngles.y;
                    float currentYaw = transform.eulerAngles.y;
                    float newYaw = Mathf.MoveTowardsAngle(currentYaw, targetYaw, turnYawSpeed * Time.deltaTime);
                    transform.rotation = Quaternion.Euler(0f, newYaw, 0f);

                    float yawDelta = Mathf.DeltaAngle(newYaw, targetYaw);
                    if (Mathf.Abs(yawDelta) < 3f)
                    {
                        _facingThreat = true;
                        // Threatened → trigger reflex immediately
                        float t = Time.realtimeSinceStartup;
                        reflex?.OnThreatEvent(QuickDraw.AI.Reflex.ThreatEventType.GUN_AIMED_AT_ME, t);
                    }
                }
            }
        }

        void TickPerception()
        {
            if (player == null) return;

            Vector3 toPlayer = (player.position - eye.position).normalized;
            float cosA = Vector3.Dot(transform.forward, toPlayer);
            cosA = Mathf.Clamp(cosA, -1f, 1f);
            float angleDeg = Mathf.Acos(cosA) * Mathf.Rad2Deg;

            bool withinPeripheral = angleDeg <= peripheralFOV;
            bool withinCore = angleDeg <= coreFOV;

            bool hasLoS = false;
            if (withinPeripheral)
            {
                // Line of sight check only when needed
                hasLoS = !Physics.Linecast(eye.position, player.position, occludersMask);
            }

            if (withinCore && hasLoS)
            {
                _suspicion = 1f; // instant
                _facingThreat = false; // will turn if not already facing
                LogSuspicion(angleDeg, 0f);
            }
            else if (withinPeripheral && hasLoS)
            {
                // build suspicion
                float gain = Mathf.Clamp01(Time.deltaTime / Mathf.Max(0.1f, suspectTime));
                _suspicion = Mathf.Clamp01(_suspicion + gain);
                _facingThreat = false;
            }
            else
            {
                // decay
                _suspicion = Mathf.Clamp01(_suspicion - decayRate * Time.deltaTime);
                if (_suspicion < 0.3f) _facingThreat = false;
            }

            // Optional: head look blend via animator param
            if (animator) animator.SetFloat("LookWeight", _suspicion);

            // If crossed into Suspicious, log angle and (later) time spent
            // For scaffold brevity we log only first detect
            if (withinPeripheral && hasLoS && Mathf.Approximately(_suspicion, 1f))
            {
                LogSuspicion(angleDeg, suspectTime * 1000f);
            }
        }

        void LogSuspicion(float angleDeg, float timeInSuspiciousMs)
        {
            JsonlLogger.Instance?.Log(new {
                t = "suspicion",
                npcId = _npcId,
                ts = Time.realtimeSinceStartup,
                angleDeg = angleDeg,
                time_in_suspicious_ms = Mathf.RoundToInt(timeInSuspiciousMs)
            });
        }

        // Public hook for direct "gun aimed" detection path if you wire raycast -> this component
        public void OnDirectThreatDetected()
        {
            float t = Time.realtimeSinceStartup;
            _suspicion = 1f;
            _facingThreat = true;
            reflex?.OnThreatEvent(QuickDraw.AI.Reflex.ThreatEventType.GUN_AIMED_AT_ME, t);
        }
    }
}
