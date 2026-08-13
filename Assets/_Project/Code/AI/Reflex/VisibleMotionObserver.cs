using System;
using UnityEngine;

namespace QuickDraw.AI.Reflex
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(ReflexSelector))]
    public sealed class VisibleMotionObserver : MonoBehaviour
    {
        public const string VisibleMotionStartedEventName = "visible_motion_started";
        public const string RootPositionSignal = "root_position";
        public const string RootRotationSignal = "root_rotation";
        public const string RootPositionAndRotationSignal = "root_position_rotation";

        [SerializeField] private ReflexSelector reflexSelector;
        [SerializeField, Min(0.001f)] private float positionThreshold = 0.01f;
        [SerializeField, Min(0.1f)] private float rotationThresholdDegrees = 1f;

        private bool _subscribed;
        private Vector3 _commandStartPosition;
        private Quaternion _commandStartRotation;

        public bool IsAwaitingVisibleMotion { get; private set; }
        public int VisibleMotionCount { get; private set; }
        public int LastObservedThreatEpisodeId { get; private set; }
        public string LastSignal { get; private set; } = string.Empty;
        public float LastConfirmedThreatTime { get; private set; } = -1f;
        public float LastCommandTime { get; private set; } = -1f;
        public float LastVisibleMotionTime { get; private set; } = -1f;
        public float LastPositionDelta { get; private set; }
        public float LastRotationDelta { get; private set; }
        public float CommandToVisibleMilliseconds { get; private set; } = -1f;
        public float ConfirmationToVisibleMilliseconds { get; private set; } = -1f;

        public event Action VisibleMotionStarted;

        private void Awake()
        {
            ResolveReferences();
            ResetObservation();
        }

        private void OnEnable()
        {
            ResolveReferences();
            Subscribe();
        }

        private void OnDisable()
        {
            Unsubscribe();
        }

        private void LateUpdate()
        {
            TickObservation(Time.realtimeSinceStartup);
        }

        [ContextMenu("Reset Visible Motion State")]
        public void ResetObservation()
        {
            IsAwaitingVisibleMotion = false;
            VisibleMotionCount = 0;
            LastObservedThreatEpisodeId = 0;
            LastSignal = string.Empty;
            LastConfirmedThreatTime = -1f;
            LastCommandTime = -1f;
            LastVisibleMotionTime = -1f;
            LastPositionDelta = 0f;
            LastRotationDelta = 0f;
            CommandToVisibleMilliseconds = -1f;
            ConfirmationToVisibleMilliseconds = -1f;
            _commandStartPosition = transform.position;
            _commandStartRotation = transform.rotation;
        }

        private void HandleReflexCommanded()
        {
            if (reflexSelector == null ||
                reflexSelector.LastCommandedThreatEpisodeId <= 0 ||
                reflexSelector.LastCommandedThreatEpisodeId == LastObservedThreatEpisodeId)
            {
                return;
            }

            _commandStartPosition = reflexSelector.LastCommandStartPosition;
            _commandStartRotation = reflexSelector.LastCommandStartRotation;
            LastConfirmedThreatTime = reflexSelector.LastConfirmedThreatTime;
            LastCommandTime = reflexSelector.LastCommandTime;
            LastPositionDelta = 0f;
            LastRotationDelta = 0f;
            IsAwaitingVisibleMotion = true;
        }

        private void TickObservation(float observedTime)
        {
            if (!IsAwaitingVisibleMotion || reflexSelector == null)
            {
                return;
            }

            int episodeId = reflexSelector.LastCommandedThreatEpisodeId;
            if (episodeId <= 0 || episodeId == LastObservedThreatEpisodeId)
            {
                IsAwaitingVisibleMotion = false;
                return;
            }

            float positionDelta = Vector3.Distance(transform.position, _commandStartPosition);
            float rotationDelta = Quaternion.Angle(transform.rotation, _commandStartRotation);
            bool positionObserved = positionDelta >= positionThreshold;
            bool rotationObserved = rotationDelta >= rotationThresholdDegrees;
            LastPositionDelta = positionDelta;
            LastRotationDelta = rotationDelta;

            if (!positionObserved && !rotationObserved)
            {
                return;
            }

            IsAwaitingVisibleMotion = false;
            LastObservedThreatEpisodeId = episodeId;
            LastSignal = GetSignal(positionObserved, rotationObserved);
            LastVisibleMotionTime = Mathf.Max(observedTime, LastCommandTime);
            CommandToVisibleMilliseconds = Mathf.Max(
                0f,
                (LastVisibleMotionTime - LastCommandTime) * 1000f);
            ConfirmationToVisibleMilliseconds = Mathf.Max(
                0f,
                (LastVisibleMotionTime - LastConfirmedThreatTime) * 1000f);
            VisibleMotionCount++;
            VisibleMotionStarted?.Invoke();
        }

        private string GetSignal(bool positionObserved, bool rotationObserved)
        {
            if (positionObserved && rotationObserved)
            {
                return RootPositionAndRotationSignal;
            }

            return positionObserved ? RootPositionSignal : RootRotationSignal;
        }

        private void Subscribe()
        {
            if (_subscribed || reflexSelector == null)
            {
                return;
            }

            reflexSelector.ReflexCommanded += HandleReflexCommanded;
            _subscribed = true;
        }

        private void Unsubscribe()
        {
            if (!_subscribed || reflexSelector == null)
            {
                return;
            }

            reflexSelector.ReflexCommanded -= HandleReflexCommanded;
            _subscribed = false;
        }

        private void ResolveReferences()
        {
            if (reflexSelector == null)
            {
                reflexSelector = GetComponent<ReflexSelector>();
            }
        }

#if UNITY_EDITOR
        private void OnValidate()
        {
            positionThreshold = Mathf.Max(0.001f, positionThreshold);
            rotationThresholdDegrees = Mathf.Max(0.1f, rotationThresholdDegrees);
            ResolveReferences();
        }
#endif
    }
}
