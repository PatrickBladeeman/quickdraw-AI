using System;
using UnityEngine;

namespace QuickDraw.AI.Reflex
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(CharacterController))]
    public sealed class ReflexSelector : MonoBehaviour
    {
        public const string FlinchStepBackVariant = "Flinch_StepBack";
        public const string ReflexCommandedEventName = "reflex_commanded";

        [Header("Stable Style")]
        [SerializeField] private int styleSeed = 1001;

        [Header("Flinch Step Back")]
        [SerializeField, Range(0.1f, 0.6f)] private float stepBackDistance = 0.35f;
        [SerializeField, Range(0f, 0.25f)] private float stepDistanceVariation = 0.05f;
        [SerializeField, Range(0f, 30f)] private float maximumYawOffset = 30f;

        private CharacterController _characterController;

        public int CommandCount { get; private set; }
        public int LastCommandedThreatEpisodeId { get; private set; }
        public string LastCommandedVariant { get; private set; } = string.Empty;
        public float LastConfirmedThreatTime { get; private set; } = -1f;
        public float LastCommandTime { get; private set; } = -1f;
        public float LastRequestedStepDistance { get; private set; }
        public float LastAppliedStepDistance { get; private set; }
        public float LastYawOffset { get; private set; }
        public CollisionFlags LastCollisionFlags { get; private set; }

        public event Action ReflexCommanded;

        private void Awake()
        {
            ResolveReferences();
        }

        public bool TryCommandFlinchStepBack(int threatEpisodeId, float confirmedThreatTime)
        {
            ResolveReferences();
            if (threatEpisodeId <= 0 ||
                threatEpisodeId == LastCommandedThreatEpisodeId ||
                _characterController == null ||
                !_characterController.enabled)
            {
                return false;
            }

            float yawOffset = Mathf.Lerp(
                -maximumYawOffset,
                maximumYawOffset,
                Sample01(threatEpisodeId, 0xA511E9B3u));
            float distanceOffset = Mathf.Lerp(
                -stepDistanceVariation,
                stepDistanceVariation,
                Sample01(threatEpisodeId, 0x63D83595u));
            float requestedDistance = Mathf.Clamp(
                stepBackDistance + distanceOffset,
                0.1f,
                0.6f);

            Vector3 horizontalForward = Vector3.ProjectOnPlane(transform.forward, Vector3.up);
            if (horizontalForward.sqrMagnitude <= Mathf.Epsilon)
            {
                horizontalForward = Vector3.forward;
            }

            horizontalForward.Normalize();
            Vector3 flinchForward = Quaternion.AngleAxis(yawOffset, Vector3.up) * horizontalForward;
            transform.rotation = Quaternion.LookRotation(flinchForward, Vector3.up);

            Vector3 positionBeforeCommand = transform.position;
            float commandTime = Time.realtimeSinceStartup;
            CollisionFlags collisionFlags = _characterController.Move(
                -flinchForward * requestedDistance);
            float appliedDistance = Vector3.ProjectOnPlane(
                transform.position - positionBeforeCommand,
                Vector3.up).magnitude;

            LastCommandedThreatEpisodeId = threatEpisodeId;
            LastCommandedVariant = FlinchStepBackVariant;
            LastConfirmedThreatTime = confirmedThreatTime;
            LastCommandTime = commandTime;
            LastRequestedStepDistance = requestedDistance;
            LastAppliedStepDistance = appliedDistance;
            LastYawOffset = yawOffset;
            LastCollisionFlags = collisionFlags;
            CommandCount++;
            ReflexCommanded?.Invoke();
            return true;
        }

        [ContextMenu("Reset Reflex State")]
        public void ResetReflex()
        {
            CommandCount = 0;
            LastCommandedThreatEpisodeId = 0;
            LastCommandedVariant = string.Empty;
            LastConfirmedThreatTime = -1f;
            LastCommandTime = -1f;
            LastRequestedStepDistance = 0f;
            LastAppliedStepDistance = 0f;
            LastYawOffset = 0f;
            LastCollisionFlags = CollisionFlags.None;
        }

        private float Sample01(int threatEpisodeId, uint salt)
        {
            unchecked
            {
                uint value = (uint)styleSeed;
                value ^= (uint)threatEpisodeId * 0x9E3779B9u;
                value ^= salt;
                value ^= value >> 16;
                value *= 0x7FEB352Du;
                value ^= value >> 15;
                value *= 0x846CA68Bu;
                value ^= value >> 16;
                return (value & 0x00FFFFFFu) / 16777215f;
            }
        }

        private void ResolveReferences()
        {
            if (_characterController == null)
            {
                _characterController = GetComponent<CharacterController>();
            }
        }

#if UNITY_EDITOR
        private void OnValidate()
        {
            ResolveReferences();
        }
#endif
    }
}
