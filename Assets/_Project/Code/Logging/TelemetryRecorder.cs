using System;
using QuickDraw.AI.Activity;
using QuickDraw.AI.Behavior;
using QuickDraw.AI.Perception;
using QuickDraw.AI.Reflex;
using QuickDraw.AI.Stimuli;
using UnityEngine;

namespace QuickDraw.Logging
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(JsonlLogger))]
    public sealed class TelemetryRecorder : MonoBehaviour
    {
        [Header("Output")]
        [SerializeField] private JsonlLogger logger;

        [Header("Observed Runtime")]
        [SerializeField] private AimThreatEmitter aimThreatEmitter;
        [SerializeField] private SoftFOVPerception perception;
        [SerializeField] private PatrolActivity patrolActivity;
        [SerializeField] private NpcBehaviorController behaviorController;
        [SerializeField] private ReflexSelector reflexSelector;
        [SerializeField] private VisibleMotionObserver visibleMotionObserver;

        private bool _subscribed;
        private bool _initialActivityRecorded;
        private bool _noticeRecorded;
        private bool _thresholdRecorded;
        private bool _turnRecorded;
        private int _lastConfirmedEpisodeId;
        private int _lastReleasedEpisodeId;
        private float _stimulusStartTime = -1f;
        private float _noticeTime = -1f;
        private float _thresholdTime = -1f;
        private float _turnTime = -1f;
        private float _confirmationTime = -1f;
        private float _releaseTime = -1f;

        public int RecordedEventCount { get; private set; }
        public string LastRecordedEvent { get; private set; } = string.Empty;

        private string NpcId => perception != null ? perception.gameObject.name : string.Empty;

        private void Awake()
        {
            ResolveReferences();
            ResetRecordingState();
        }

        private void OnEnable()
        {
            ResolveReferences();
            Subscribe();
        }

        private void Start()
        {
            RecordInitialActivityIfNeeded();
        }

        private void OnDisable()
        {
            Unsubscribe();
        }

        [ContextMenu("Reset Telemetry Recorder")]
        public void ResetRecordingState()
        {
            _initialActivityRecorded = false;
            _lastConfirmedEpisodeId = 0;
            _lastReleasedEpisodeId = 0;
            ResetEpisodeTiming();
            RecordedEventCount = 0;
            LastRecordedEvent = string.Empty;
        }

        private void HandleAimStarted(AimThreatStimulus stimulus)
        {
            ResetEpisodeTiming();
            _stimulusStartTime = stimulus.Timestamp;
            Enqueue(new AimStimulusEventRecord(
                TelemetryEventNames.AimStimulusStarted,
                stimulus.Timestamp,
                stimulus.SourceId,
                stimulus.MaxDistance));
        }

        private void HandleAimEnded(AimThreatStimulus stimulus)
        {
            Enqueue(new AimStimulusEventRecord(
                TelemetryEventNames.AimStimulusEnded,
                stimulus.Timestamp,
                stimulus.SourceId,
                stimulus.MaxDistance));
        }

        private void HandlePerceptionStateChanged(PerceptionState state)
        {
            if (perception == null)
            {
                return;
            }

            float timestamp = Time.realtimeSinceStartup;
            switch (state)
            {
                case PerceptionState.Suspicious when !_noticeRecorded:
                    _noticeRecorded = true;
                    _noticeTime = timestamp;
                    Enqueue(new PerceptionNoticeEventRecord(
                        timestamp,
                        NpcId,
                        perception.LastAngle,
                        perception.HasLineOfSight,
                        MillisecondsBetween(_stimulusStartTime, timestamp)));
                    break;

                case PerceptionState.Orienting:
                    if (!_thresholdRecorded)
                    {
                        _thresholdRecorded = true;
                        _thresholdTime = timestamp;
                        Enqueue(new SuspicionThresholdEventRecord(
                            timestamp,
                            NpcId,
                            perception.Suspicion,
                            MillisecondsBetween(_noticeTime, timestamp)));
                    }

                    if (!_turnRecorded)
                    {
                        _turnRecorded = true;
                        _turnTime = timestamp;
                        Enqueue(new TurnStartedEventRecord(
                            timestamp,
                            NpcId,
                            MillisecondsBetween(_thresholdTime, timestamp)));
                    }
                    break;

                case PerceptionState.ThreatConfirmed
                    when perception.ThreatEpisodeId > 0 &&
                        perception.ThreatEpisodeId != _lastConfirmedEpisodeId:
                    _lastConfirmedEpisodeId = perception.ThreatEpisodeId;
                    _confirmationTime = perception.LastConfirmationTime >= 0f
                        ? perception.LastConfirmationTime
                        : timestamp;
                    Enqueue(new ThreatConfirmedEventRecord(
                        _confirmationTime,
                        NpcId,
                        perception.ThreatEpisodeId,
                        MillisecondsBetween(_turnTime, _confirmationTime)));
                    break;

                case PerceptionState.Recovering
                    when perception.ThreatEpisodeId > 0 &&
                        perception.ThreatEpisodeId != _lastReleasedEpisodeId:
                    _lastReleasedEpisodeId = perception.ThreatEpisodeId;
                    _releaseTime = timestamp;
                    Enqueue(new ThreatReleasedEventRecord(
                        timestamp,
                        NpcId,
                        perception.ThreatEpisodeId));
                    break;
            }
        }

        private void HandleBehaviorInterrupted(NpcBehaviorController source)
        {
            if (source == null)
            {
                return;
            }

            Enqueue(new ActivityInterruptedEventRecord(
                source.InterruptionTime,
                NpcId,
                source.LastHandledThreatEpisodeId,
                source.InterruptedActivityName,
                source.InterruptionReason,
                source.InterruptionOutcome.ToString(),
                MillisecondsBetween(_confirmationTime, source.InterruptionTime)));
        }

        private void HandleReflexCommanded()
        {
            if (reflexSelector == null)
            {
                return;
            }

            Enqueue(new ReflexCommandedEventRecord(
                reflexSelector.LastCommandTime,
                NpcId,
                reflexSelector.LastCommandedThreatEpisodeId,
                reflexSelector.LastCommandedVariant,
                reflexSelector.LastRequestedStepDistance,
                reflexSelector.LastAppliedStepDistance,
                reflexSelector.LastYawOffset,
                MillisecondsBetween(
                    reflexSelector.LastConfirmedThreatTime,
                    reflexSelector.LastCommandTime)));
        }

        private void HandleVisibleMotionStarted()
        {
            if (visibleMotionObserver == null)
            {
                return;
            }

            Enqueue(new VisibleMotionStartedEventRecord(
                visibleMotionObserver.LastVisibleMotionTime,
                NpcId,
                visibleMotionObserver.LastObservedThreatEpisodeId,
                visibleMotionObserver.LastSignal,
                visibleMotionObserver.LastPositionDelta,
                visibleMotionObserver.LastRotationDelta,
                visibleMotionObserver.CommandToVisibleMilliseconds,
                visibleMotionObserver.ConfirmationToVisibleMilliseconds));
        }

        private void HandleActivityStarted(PatrolActivity source)
        {
            if (source == null)
            {
                return;
            }

            _initialActivityRecorded = true;
            Enqueue(new ActivityStartedEventRecord(
                source.StartTime,
                NpcId,
                source.ActivityName));
        }

        private void HandleActivityResumed(PatrolActivity source)
        {
            if (source == null)
            {
                return;
            }

            Enqueue(new ActivityResumedEventRecord(
                source.ResumeTime,
                NpcId,
                source.ActivityName,
                MillisecondsBetween(_releaseTime, source.ResumeTime)));
        }

        private void HandleActivityCancelled(PatrolActivity source)
        {
            if (source == null)
            {
                return;
            }

            Enqueue(new ActivityCancelledEventRecord(
                Time.realtimeSinceStartup,
                NpcId,
                source.ActivityName));
        }

        private void RecordInitialActivityIfNeeded()
        {
            if (_initialActivityRecorded || patrolActivity == null || !patrolActivity.IsRunning)
            {
                return;
            }

            HandleActivityStarted(patrolActivity);
        }

        private void Enqueue(TelemetryEventRecord eventRecord)
        {
            if (logger == null || eventRecord == null)
            {
                return;
            }

            try
            {
                if (logger.Record(eventRecord))
                {
                    RecordedEventCount++;
                    LastRecordedEvent = eventRecord.EventType;
                }
            }
            catch (Exception exception)
            {
                Debug.LogWarning($"Telemetry event was skipped: {exception.Message}", this);
            }
        }

        private void ResetEpisodeTiming()
        {
            _noticeRecorded = false;
            _thresholdRecorded = false;
            _turnRecorded = false;
            _stimulusStartTime = -1f;
            _noticeTime = -1f;
            _thresholdTime = -1f;
            _turnTime = -1f;
            _confirmationTime = -1f;
            _releaseTime = -1f;
        }

        private static float MillisecondsBetween(float startTime, float endTime)
        {
            return startTime >= 0f && endTime >= startTime
                ? (endTime - startTime) * 1000f
                : -1f;
        }

        private void Subscribe()
        {
            if (_subscribed)
            {
                return;
            }

            if (aimThreatEmitter != null)
            {
                aimThreatEmitter.AimStarted += HandleAimStarted;
                aimThreatEmitter.AimEnded += HandleAimEnded;
            }

            if (perception != null)
            {
                perception.StateChanged += HandlePerceptionStateChanged;
            }

            if (behaviorController != null)
            {
                behaviorController.ActivityInterrupted += HandleBehaviorInterrupted;
            }

            if (reflexSelector != null)
            {
                reflexSelector.ReflexCommanded += HandleReflexCommanded;
            }

            if (visibleMotionObserver != null)
            {
                visibleMotionObserver.VisibleMotionStarted += HandleVisibleMotionStarted;
            }

            if (patrolActivity != null)
            {
                patrolActivity.ActivityStarted += HandleActivityStarted;
                patrolActivity.ActivityResumed += HandleActivityResumed;
                patrolActivity.ActivityCancelled += HandleActivityCancelled;
            }

            _subscribed = true;
        }

        private void Unsubscribe()
        {
            if (!_subscribed)
            {
                return;
            }

            if (aimThreatEmitter != null)
            {
                aimThreatEmitter.AimStarted -= HandleAimStarted;
                aimThreatEmitter.AimEnded -= HandleAimEnded;
            }

            if (perception != null)
            {
                perception.StateChanged -= HandlePerceptionStateChanged;
            }

            if (behaviorController != null)
            {
                behaviorController.ActivityInterrupted -= HandleBehaviorInterrupted;
            }

            if (reflexSelector != null)
            {
                reflexSelector.ReflexCommanded -= HandleReflexCommanded;
            }

            if (visibleMotionObserver != null)
            {
                visibleMotionObserver.VisibleMotionStarted -= HandleVisibleMotionStarted;
            }

            if (patrolActivity != null)
            {
                patrolActivity.ActivityStarted -= HandleActivityStarted;
                patrolActivity.ActivityResumed -= HandleActivityResumed;
                patrolActivity.ActivityCancelled -= HandleActivityCancelled;
            }

            _subscribed = false;
        }

        private void ResolveReferences()
        {
            if (logger == null)
            {
                logger = GetComponent<JsonlLogger>();
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
