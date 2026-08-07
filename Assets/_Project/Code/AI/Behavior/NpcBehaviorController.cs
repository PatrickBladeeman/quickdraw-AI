using System;
using QuickDraw.AI.Activity;
using QuickDraw.AI.Perception;
using QuickDraw.AI.Reflex;
using UnityEngine;

namespace QuickDraw.AI.Behavior
{
    public enum ActivityInterruptionOutcome
    {
        None,
        Suspended,
        Cancelled
    }

    [DisallowMultipleComponent]
    [RequireComponent(typeof(SoftFOVPerception))]
    [RequireComponent(typeof(PatrolActivity))]
    [RequireComponent(typeof(ReflexSelector))]
    public sealed class NpcBehaviorController : MonoBehaviour
    {
        public const string ConfirmedAimThreatReason = "ConfirmedAimThreat";

        [SerializeField] private SoftFOVPerception perception;
        [SerializeField] private PatrolActivity patrolActivity;
        [SerializeField] private ReflexSelector reflexSelector;

        private bool _subscribed;
        private float _lastHandledConfirmationTime = -1f;

        public int InterruptionCount { get; private set; }
        public int LastHandledThreatEpisodeId { get; private set; }
        public string InterruptedActivityName { get; private set; } = string.Empty;
        public string InterruptionReason { get; private set; } = string.Empty;
        public float InterruptionTime { get; private set; } = -1f;
        public ActivityInterruptionOutcome InterruptionOutcome { get; private set; }

        public event Action<NpcBehaviorController> ActivityInterrupted;

        private void Awake()
        {
            ResolveReferences();
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

        [ContextMenu("Reset Coordination")]
        public void ResetCoordination()
        {
            InterruptionCount = 0;
            LastHandledThreatEpisodeId = 0;
            InterruptedActivityName = string.Empty;
            InterruptionReason = string.Empty;
            InterruptionTime = -1f;
            InterruptionOutcome = ActivityInterruptionOutcome.None;
            _lastHandledConfirmationTime = -1f;
            reflexSelector?.ResetReflex();
        }

        private void HandleThreatConfirmed(SoftFOVPerception source)
        {
            if (source == null || source != perception || patrolActivity == null)
            {
                return;
            }

            int episodeId = source.ThreatEpisodeId;
            float confirmationTime = source.LastConfirmationTime;
            if (episodeId <= 0 || IsAlreadyHandled(episodeId, confirmationTime))
            {
                return;
            }

            LastHandledThreatEpisodeId = episodeId;
            _lastHandledConfirmationTime = confirmationTime;

            string activityName = patrolActivity.ActivityName;
            bool wasRunning = patrolActivity.IsRunning;
            patrolActivity.InterruptActivity(ConfirmedAimThreatReason);

            if (!wasRunning || !patrolActivity.IsInterrupted)
            {
                return;
            }

            InterruptedActivityName = activityName;
            InterruptionReason = patrolActivity.InterruptionReason;
            InterruptionTime = patrolActivity.InterruptionTime;
            InterruptionOutcome = ActivityInterruptionOutcome.Suspended;
            InterruptionCount++;
            ActivityInterrupted?.Invoke(this);

            if (!patrolActivity.IsRunning)
            {
                reflexSelector?.TryCommandFlinchStepBack(episodeId, confirmationTime);
            }
        }

        private bool IsAlreadyHandled(int episodeId, float confirmationTime)
        {
            return episodeId == LastHandledThreatEpisodeId &&
                Mathf.Approximately(confirmationTime, _lastHandledConfirmationTime);
        }

        private void Subscribe()
        {
            if (_subscribed || perception == null)
            {
                return;
            }

            perception.ThreatConfirmed += HandleThreatConfirmed;
            _subscribed = true;
        }

        private void Unsubscribe()
        {
            if (!_subscribed || perception == null)
            {
                return;
            }

            perception.ThreatConfirmed -= HandleThreatConfirmed;
            _subscribed = false;
        }

        private void ResolveReferences()
        {
            if (perception == null)
            {
                perception = GetComponent<SoftFOVPerception>();
            }

            if (patrolActivity == null)
            {
                patrolActivity = GetComponent<PatrolActivity>();
            }

            if (reflexSelector == null)
            {
                reflexSelector = GetComponent<ReflexSelector>();
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
