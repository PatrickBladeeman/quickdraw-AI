using Newtonsoft.Json;

namespace QuickDraw.Logging
{
    public static class TelemetryEventNames
    {
        public const string SessionStart = "session_start";
        public const string AimStimulusStarted = "aim_stimulus_started";
        public const string AimStimulusEnded = "aim_stimulus_ended";
        public const string ActivityStarted = "activity_started";
        public const string PerceptionNotice = "perception_notice";
        public const string SuspicionThreshold = "suspicion_threshold";
        public const string TurnStarted = "turn_started";
        public const string ThreatConfirmed = "threat_confirmed";
        public const string ActivityInterrupted = "activity_interrupted";
        public const string ReflexCommanded = "reflex_commanded";
        public const string VisibleMotionStarted = "visible_motion_started";
        public const string ThreatReleased = "threat_released";
        public const string ActivityResumed = "activity_resumed";
        public const string ActivityCancelled = "activity_cancelled";
        public const string SessionSummary = "session_summary";
    }

    public static class TelemetryStages
    {
        public const string StimulusToNotice = "stimulus_to_notice";
        public const string NoticeToSuspicionThreshold = "notice_to_suspicion_threshold";
        public const string SuspicionThresholdToTurn = "suspicion_threshold_to_turn";
        public const string TurnToConfirmation = "turn_to_confirmation";
        public const string ConfirmationToInterruption = "confirmation_to_interruption";
        public const string ConfirmationToReflexCommand = "confirmation_to_reflex_command";
        public const string CommandToVisibleMotion = "command_to_visible_motion";
        public const string ConfirmationToVisibleMotion = "confirmation_to_visible_motion";
        public const string ThreatReleaseToActivityResume = "threat_release_to_activity_resume";
    }

    public interface ILatencySample
    {
        string Stage { get; }
        float LatencyMilliseconds { get; }
    }

    [JsonObject(MemberSerialization.OptIn)]
    public abstract class TelemetryEventRecord
    {
        protected TelemetryEventRecord(string eventType, float timestamp)
        {
            EventType = eventType;
            Timestamp = timestamp;
        }

        [JsonProperty("t", Order = 0)]
        public string EventType { get; }

        [JsonProperty("ts", Order = 1)]
        public float Timestamp { get; }
    }

    [JsonObject(MemberSerialization.OptIn)]
    public sealed class SessionStartEventRecord : TelemetryEventRecord
    {
        public SessionStartEventRecord(
            float timestamp,
            string sessionId,
            string unityVersion)
            : base(TelemetryEventNames.SessionStart, timestamp)
        {
            SessionId = sessionId;
            UnityVersion = unityVersion;
        }

        [JsonProperty("sessionId", Order = 2)]
        public string SessionId { get; }

        [JsonProperty("unity", Order = 3)]
        public string UnityVersion { get; }
    }

    [JsonObject(MemberSerialization.OptIn)]
    public sealed class AimStimulusEventRecord : TelemetryEventRecord
    {
        public AimStimulusEventRecord(
            string eventType,
            float timestamp,
            int sourceId,
            float maxDistance)
            : base(eventType, timestamp)
        {
            SourceId = sourceId;
            MaxDistance = maxDistance;
        }

        [JsonProperty("sourceId", Order = 2)]
        public int SourceId { get; }

        [JsonProperty("maxDistance", Order = 3)]
        public float MaxDistance { get; }
    }

    [JsonObject(MemberSerialization.OptIn)]
    public sealed class ActivityStartedEventRecord : TelemetryEventRecord
    {
        public ActivityStartedEventRecord(float timestamp, string npcId, string activity)
            : base(TelemetryEventNames.ActivityStarted, timestamp)
        {
            NpcId = npcId;
            Activity = activity;
        }

        [JsonProperty("npcId", Order = 2)]
        public string NpcId { get; }

        [JsonProperty("activity", Order = 3)]
        public string Activity { get; }
    }

    [JsonObject(MemberSerialization.OptIn)]
    public sealed class PerceptionNoticeEventRecord : TelemetryEventRecord, ILatencySample
    {
        public PerceptionNoticeEventRecord(
            float timestamp,
            string npcId,
            float angleDegrees,
            bool hasLineOfSight,
            float stimulusToNoticeMilliseconds)
            : base(TelemetryEventNames.PerceptionNotice, timestamp)
        {
            NpcId = npcId;
            AngleDegrees = angleDegrees;
            HasLineOfSight = hasLineOfSight;
            StimulusToNoticeMilliseconds = stimulusToNoticeMilliseconds;
        }

        [JsonProperty("npcId", Order = 2)]
        public string NpcId { get; }

        [JsonProperty("angleDeg", Order = 3)]
        public float AngleDegrees { get; }

        [JsonProperty("hasLos", Order = 4)]
        public bool HasLineOfSight { get; }

        [JsonProperty("stimulus_to_notice_ms", Order = 5)]
        public float StimulusToNoticeMilliseconds { get; }

        [JsonIgnore]
        public string Stage => TelemetryStages.StimulusToNotice;

        [JsonIgnore]
        public float LatencyMilliseconds => StimulusToNoticeMilliseconds;
    }

    [JsonObject(MemberSerialization.OptIn)]
    public sealed class SuspicionThresholdEventRecord : TelemetryEventRecord, ILatencySample
    {
        public SuspicionThresholdEventRecord(
            float timestamp,
            string npcId,
            float suspicion,
            float noticeToThresholdMilliseconds)
            : base(TelemetryEventNames.SuspicionThreshold, timestamp)
        {
            NpcId = npcId;
            Suspicion = suspicion;
            NoticeToThresholdMilliseconds = noticeToThresholdMilliseconds;
        }

        [JsonProperty("npcId", Order = 2)]
        public string NpcId { get; }

        [JsonProperty("suspicion", Order = 3)]
        public float Suspicion { get; }

        [JsonProperty("notice_to_threshold_ms", Order = 4)]
        public float NoticeToThresholdMilliseconds { get; }

        [JsonIgnore]
        public string Stage => TelemetryStages.NoticeToSuspicionThreshold;

        [JsonIgnore]
        public float LatencyMilliseconds => NoticeToThresholdMilliseconds;
    }

    [JsonObject(MemberSerialization.OptIn)]
    public sealed class TurnStartedEventRecord : TelemetryEventRecord, ILatencySample
    {
        public TurnStartedEventRecord(
            float timestamp,
            string npcId,
            float thresholdToTurnMilliseconds)
            : base(TelemetryEventNames.TurnStarted, timestamp)
        {
            NpcId = npcId;
            ThresholdToTurnMilliseconds = thresholdToTurnMilliseconds;
        }

        [JsonProperty("npcId", Order = 2)]
        public string NpcId { get; }

        [JsonProperty("threshold_to_turn_ms", Order = 3)]
        public float ThresholdToTurnMilliseconds { get; }

        [JsonIgnore]
        public string Stage => TelemetryStages.SuspicionThresholdToTurn;

        [JsonIgnore]
        public float LatencyMilliseconds => ThresholdToTurnMilliseconds;
    }

    [JsonObject(MemberSerialization.OptIn)]
    public sealed class ThreatConfirmedEventRecord : TelemetryEventRecord, ILatencySample
    {
        public ThreatConfirmedEventRecord(
            float timestamp,
            string npcId,
            int episodeId,
            float turnToConfirmationMilliseconds)
            : base(TelemetryEventNames.ThreatConfirmed, timestamp)
        {
            NpcId = npcId;
            EpisodeId = episodeId;
            TurnToConfirmationMilliseconds = turnToConfirmationMilliseconds;
        }

        [JsonProperty("npcId", Order = 2)]
        public string NpcId { get; }

        [JsonProperty("episodeId", Order = 3)]
        public int EpisodeId { get; }

        [JsonProperty("turn_to_confirmation_ms", Order = 4)]
        public float TurnToConfirmationMilliseconds { get; }

        [JsonIgnore]
        public string Stage => TelemetryStages.TurnToConfirmation;

        [JsonIgnore]
        public float LatencyMilliseconds => TurnToConfirmationMilliseconds;
    }

    [JsonObject(MemberSerialization.OptIn)]
    public sealed class ActivityInterruptedEventRecord : TelemetryEventRecord, ILatencySample
    {
        public ActivityInterruptedEventRecord(
            float timestamp,
            string npcId,
            int episodeId,
            string activity,
            string reason,
            string outcome,
            float confirmationToInterruptionMilliseconds)
            : base(TelemetryEventNames.ActivityInterrupted, timestamp)
        {
            NpcId = npcId;
            EpisodeId = episodeId;
            Activity = activity;
            Reason = reason;
            Outcome = outcome;
            ConfirmationToInterruptionMilliseconds = confirmationToInterruptionMilliseconds;
        }

        [JsonProperty("npcId", Order = 2)]
        public string NpcId { get; }

        [JsonProperty("episodeId", Order = 3)]
        public int EpisodeId { get; }

        [JsonProperty("activity", Order = 4)]
        public string Activity { get; }

        [JsonProperty("reason", Order = 5)]
        public string Reason { get; }

        [JsonProperty("outcome", Order = 6)]
        public string Outcome { get; }

        [JsonProperty("confirmation_to_interruption_ms", Order = 7)]
        public float ConfirmationToInterruptionMilliseconds { get; }

        [JsonIgnore]
        public string Stage => TelemetryStages.ConfirmationToInterruption;

        [JsonIgnore]
        public float LatencyMilliseconds => ConfirmationToInterruptionMilliseconds;
    }

    [JsonObject(MemberSerialization.OptIn)]
    public sealed class ReflexCommandedEventRecord : TelemetryEventRecord, ILatencySample
    {
        public ReflexCommandedEventRecord(
            float timestamp,
            string npcId,
            int episodeId,
            string variant,
            float requestedStepMeters,
            float appliedStepMeters,
            float yawDegrees,
            float confirmationToCommandMilliseconds)
            : base(TelemetryEventNames.ReflexCommanded, timestamp)
        {
            NpcId = npcId;
            EpisodeId = episodeId;
            Variant = variant;
            RequestedStepMeters = requestedStepMeters;
            AppliedStepMeters = appliedStepMeters;
            YawDegrees = yawDegrees;
            ConfirmationToCommandMilliseconds = confirmationToCommandMilliseconds;
        }

        [JsonProperty("npcId", Order = 2)]
        public string NpcId { get; }

        [JsonProperty("episodeId", Order = 3)]
        public int EpisodeId { get; }

        [JsonProperty("variant", Order = 4)]
        public string Variant { get; }

        [JsonProperty("requested_step_m", Order = 5)]
        public float RequestedStepMeters { get; }

        [JsonProperty("applied_step_m", Order = 6)]
        public float AppliedStepMeters { get; }

        [JsonProperty("yaw_deg", Order = 7)]
        public float YawDegrees { get; }

        [JsonProperty("confirmation_to_command_ms", Order = 8)]
        public float ConfirmationToCommandMilliseconds { get; }

        [JsonIgnore]
        public string Stage => TelemetryStages.ConfirmationToReflexCommand;

        [JsonIgnore]
        public float LatencyMilliseconds => ConfirmationToCommandMilliseconds;
    }

    [JsonObject(MemberSerialization.OptIn)]
    public sealed class VisibleMotionStartedEventRecord : TelemetryEventRecord
    {
        public VisibleMotionStartedEventRecord(
            float timestamp,
            string npcId,
            int episodeId,
            string signal,
            float positionDeltaMeters,
            float rotationDeltaDegrees,
            float commandToVisibleMilliseconds,
            float confirmationToVisibleMilliseconds)
            : base(TelemetryEventNames.VisibleMotionStarted, timestamp)
        {
            NpcId = npcId;
            EpisodeId = episodeId;
            Signal = signal;
            PositionDeltaMeters = positionDeltaMeters;
            RotationDeltaDegrees = rotationDeltaDegrees;
            CommandToVisibleMilliseconds = commandToVisibleMilliseconds;
            ConfirmationToVisibleMilliseconds = confirmationToVisibleMilliseconds;
        }

        [JsonProperty("npcId", Order = 2)]
        public string NpcId { get; }

        [JsonProperty("episodeId", Order = 3)]
        public int EpisodeId { get; }

        [JsonProperty("signal", Order = 4)]
        public string Signal { get; }

        [JsonProperty("position_delta_m", Order = 5)]
        public float PositionDeltaMeters { get; }

        [JsonProperty("rotation_delta_deg", Order = 6)]
        public float RotationDeltaDegrees { get; }

        [JsonProperty("command_to_visible_ms", Order = 7)]
        public float CommandToVisibleMilliseconds { get; }

        [JsonProperty("confirmation_to_visible_ms", Order = 8)]
        public float ConfirmationToVisibleMilliseconds { get; }
    }

    [JsonObject(MemberSerialization.OptIn)]
    public sealed class ThreatReleasedEventRecord : TelemetryEventRecord
    {
        public ThreatReleasedEventRecord(float timestamp, string npcId, int episodeId)
            : base(TelemetryEventNames.ThreatReleased, timestamp)
        {
            NpcId = npcId;
            EpisodeId = episodeId;
        }

        [JsonProperty("npcId", Order = 2)]
        public string NpcId { get; }

        [JsonProperty("episodeId", Order = 3)]
        public int EpisodeId { get; }
    }

    [JsonObject(MemberSerialization.OptIn)]
    public sealed class ActivityResumedEventRecord : TelemetryEventRecord, ILatencySample
    {
        public ActivityResumedEventRecord(
            float timestamp,
            string npcId,
            string activity,
            float threatReleaseToResumeMilliseconds)
            : base(TelemetryEventNames.ActivityResumed, timestamp)
        {
            NpcId = npcId;
            Activity = activity;
            ThreatReleaseToResumeMilliseconds = threatReleaseToResumeMilliseconds;
        }

        [JsonProperty("npcId", Order = 2)]
        public string NpcId { get; }

        [JsonProperty("activity", Order = 3)]
        public string Activity { get; }

        [JsonProperty("threat_release_to_resume_ms", Order = 4)]
        public float ThreatReleaseToResumeMilliseconds { get; }

        [JsonIgnore]
        public string Stage => TelemetryStages.ThreatReleaseToActivityResume;

        [JsonIgnore]
        public float LatencyMilliseconds => ThreatReleaseToResumeMilliseconds;
    }

    [JsonObject(MemberSerialization.OptIn)]
    public sealed class ActivityCancelledEventRecord : TelemetryEventRecord
    {
        public ActivityCancelledEventRecord(float timestamp, string npcId, string activity)
            : base(TelemetryEventNames.ActivityCancelled, timestamp)
        {
            NpcId = npcId;
            Activity = activity;
        }

        [JsonProperty("npcId", Order = 2)]
        public string NpcId { get; }

        [JsonProperty("activity", Order = 3)]
        public string Activity { get; }
    }

    [JsonObject(MemberSerialization.OptIn)]
    public sealed class SessionSummaryEventRecord : TelemetryEventRecord
    {
        public SessionSummaryEventRecord(float timestamp, string stage, LatencySummary summary)
            : base(TelemetryEventNames.SessionSummary, timestamp)
        {
            Stage = stage;
            Count = summary.Count;
            Minimum = summary.Minimum;
            Maximum = summary.Maximum;
            Mean = summary.Mean;
            P50 = summary.P50;
            P95 = summary.P95;
            StandardDeviation = summary.StandardDeviation;
        }

        [JsonProperty("stage", Order = 2)]
        public string Stage { get; }

        [JsonProperty("count", Order = 3)]
        public int Count { get; }

        [JsonProperty("min_ms", Order = 4)]
        public float Minimum { get; }

        [JsonProperty("max_ms", Order = 5)]
        public float Maximum { get; }

        [JsonProperty("mean_ms", Order = 6)]
        public float Mean { get; }

        [JsonProperty("p50_ms", Order = 7)]
        public float P50 { get; }

        [JsonProperty("p95_ms", Order = 8)]
        public float P95 { get; }

        [JsonProperty("stddev_ms", Order = 9)]
        public float StandardDeviation { get; }
    }

    public readonly struct LatencySummary
    {
        public LatencySummary(
            int count,
            float minimum,
            float maximum,
            float mean,
            float p50,
            float p95,
            float standardDeviation)
        {
            Count = count;
            Minimum = minimum;
            Maximum = maximum;
            Mean = mean;
            P50 = p50;
            P95 = p95;
            StandardDeviation = standardDeviation;
        }

        public int Count { get; }
        public float Minimum { get; }
        public float Maximum { get; }
        public float Mean { get; }
        public float P50 { get; }
        public float P95 { get; }
        public float StandardDeviation { get; }
    }
}
