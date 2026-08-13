using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Newtonsoft.Json;
using UnityEngine;

namespace QuickDraw.Logging
{
    [DisallowMultipleComponent]
    public sealed class JsonlLogger : MonoBehaviour
    {
        private static readonly UTF8Encoding Utf8WithoutBom = new UTF8Encoding(false);

        [Header("Buffering")]
        [SerializeField, Min(0.1f)] private float flushIntervalSeconds = 1f;
        [SerializeField, Min(1)] private int maxEventsPerFrame = 64;
        [SerializeField, Min(1)] private int maxQueuedEvents = 4096;

        [Header("Output")]
        [SerializeField] private bool writeToDisk = true;
        [SerializeField] private string outputDirectoryOverride = string.Empty;

        private readonly Queue<TelemetryEventRecord> _pendingEvents =
            new Queue<TelemetryEventRecord>(256);
        private readonly List<string> _bufferedLines = new List<string>(1024);
        private readonly Dictionary<string, List<float>> _latenciesByStage =
            new Dictionary<string, List<float>>(StringComparer.Ordinal);

        private float _nextFlushTime;
        private bool _summariesQueued;

        public static JsonlLogger Instance { get; private set; }

        public string SessionId { get; private set; } = string.Empty;
        public string CurrentLogPath { get; private set; } = string.Empty;
        public int PendingCount => _pendingEvents.Count;
        public int BufferedLineCount => _bufferedLines.Count;
        public int QueuedEventCount { get; private set; }
        public int SerializedEventCount { get; private set; }
        public int WrittenLineCount { get; private set; }
        public int DroppedEventCount { get; private set; }
        public int FailedFlushCount { get; private set; }
        public string LastError { get; private set; } = string.Empty;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        private static void ResetStaticState()
        {
            Instance = null;
        }

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(this);
                return;
            }

            Instance = this;
            ResetSessionState();
        }

        private void Update()
        {
            ProcessPending(maxEventsPerFrame);

            if (Time.realtimeSinceStartup >= _nextFlushTime)
            {
                FlushNow();
                _nextFlushTime = Time.realtimeSinceStartup + flushIntervalSeconds;
            }
        }

        private void OnApplicationQuit()
        {
            QueueSummaryRecords();
            ProcessPendingNow();
            FlushNow();
        }

        private void OnDestroy()
        {
            if (Instance == this)
            {
                Instance = null;
            }
        }

        public bool Record(TelemetryEventRecord eventRecord)
        {
            if (eventRecord == null)
            {
                return false;
            }

            if (_pendingEvents.Count + _bufferedLines.Count >= maxQueuedEvents)
            {
                DroppedEventCount++;
                return false;
            }

            _pendingEvents.Enqueue(eventRecord);
            QueuedEventCount++;
            return true;
        }

        public void ResetSessionState()
        {
            _pendingEvents.Clear();
            _bufferedLines.Clear();
            _latenciesByStage.Clear();
            _summariesQueued = false;

            SessionId = Guid.NewGuid().ToString("N");
            CurrentLogPath = BuildLogPath();
            QueuedEventCount = 0;
            SerializedEventCount = 0;
            WrittenLineCount = 0;
            DroppedEventCount = 0;
            FailedFlushCount = 0;
            LastError = string.Empty;
            _nextFlushTime = Time.realtimeSinceStartup + flushIntervalSeconds;

            Record(new SessionStartEventRecord(
                Time.realtimeSinceStartup,
                SessionId,
                Application.unityVersion));
        }

        public void ProcessPendingNow()
        {
            ProcessPending(int.MaxValue);
        }

        public void QueueSummaryRecords()
        {
            if (_summariesQueued)
            {
                return;
            }

            ProcessPendingNow();
            _summariesQueued = true;
            float timestamp = Time.realtimeSinceStartup;

            foreach (KeyValuePair<string, List<float>> pair in _latenciesByStage)
            {
                Record(new SessionSummaryEventRecord(
                    timestamp,
                    pair.Key,
                    CalculateSummary(pair.Value)));
            }
        }

        public bool FlushNow()
        {
            if (!writeToDisk || _bufferedLines.Count == 0)
            {
                return true;
            }

            try
            {
                string directory = Path.GetDirectoryName(CurrentLogPath);
                if (!string.IsNullOrEmpty(directory))
                {
                    Directory.CreateDirectory(directory);
                }

                File.AppendAllLines(CurrentLogPath, _bufferedLines, Utf8WithoutBom);
                WrittenLineCount += _bufferedLines.Count;
                _bufferedLines.Clear();
                LastError = string.Empty;
                return true;
            }
            catch (Exception exception)
            {
                FailedFlushCount++;
                LastError = exception.Message;
                Debug.LogWarning($"JSONL telemetry flush failed: {exception.Message}", this);
                return false;
            }
        }

        public string[] GetBufferedLinesSnapshot()
        {
            return _bufferedLines.ToArray();
        }

        public LatencySummary GetLatencySummary(string stage)
        {
            return !string.IsNullOrEmpty(stage) &&
                _latenciesByStage.TryGetValue(stage, out List<float> samples)
                ? CalculateSummary(samples)
                : default;
        }

        public void ConfigureOutput(string directoryOverride, bool enabled)
        {
            outputDirectoryOverride = directoryOverride ?? string.Empty;
            writeToDisk = enabled;
            CurrentLogPath = BuildLogPath();
        }

        private void ProcessPending(int maximumCount)
        {
            int processed = 0;
            while (_pendingEvents.Count > 0 && processed < maximumCount)
            {
                TelemetryEventRecord eventRecord = _pendingEvents.Dequeue();

                try
                {
                    _bufferedLines.Add(JsonConvert.SerializeObject(
                        eventRecord,
                        Formatting.None));
                    CollectLatencySamples(eventRecord);
                    SerializedEventCount++;
                }
                catch (Exception exception)
                {
                    DroppedEventCount++;
                    LastError = exception.Message;
                    Debug.LogWarning($"JSONL telemetry serialization failed: {exception.Message}", this);
                }

                processed++;
            }
        }

        private void CollectLatencySamples(TelemetryEventRecord eventRecord)
        {
            if (eventRecord is ILatencySample latencySample)
            {
                AddLatency(latencySample.Stage, latencySample.LatencyMilliseconds);
            }

            if (eventRecord is VisibleMotionStartedEventRecord visibleMotion)
            {
                AddLatency(
                    TelemetryStages.CommandToVisibleMotion,
                    visibleMotion.CommandToVisibleMilliseconds);
                AddLatency(
                    TelemetryStages.ConfirmationToVisibleMotion,
                    visibleMotion.ConfirmationToVisibleMilliseconds);
            }
        }

        private void AddLatency(string stage, float milliseconds)
        {
            if (string.IsNullOrEmpty(stage) ||
                milliseconds < 0f ||
                float.IsNaN(milliseconds) ||
                float.IsInfinity(milliseconds))
            {
                return;
            }

            if (!_latenciesByStage.TryGetValue(stage, out List<float> samples))
            {
                samples = new List<float>(64);
                _latenciesByStage.Add(stage, samples);
            }

            samples.Add(milliseconds);
        }

        private string BuildLogPath()
        {
            string directory = string.IsNullOrWhiteSpace(outputDirectoryOverride)
                ? Application.persistentDataPath
                : outputDirectoryOverride;
            string fileName =
                $"{DateTime.UtcNow:yyyyMMdd_HHmmss_fff}_{SessionId}_session.jsonl";
            return Path.Combine(directory, fileName);
        }

        private static LatencySummary CalculateSummary(IReadOnlyList<float> samples)
        {
            if (samples == null || samples.Count == 0)
            {
                return default;
            }

            float[] sorted = new float[samples.Count];
            float sum = 0f;
            for (int index = 0; index < samples.Count; index++)
            {
                float sample = samples[index];
                sorted[index] = sample;
                sum += sample;
            }

            Array.Sort(sorted);
            float mean = sum / sorted.Length;
            float varianceSum = 0f;
            for (int index = 0; index < sorted.Length; index++)
            {
                float delta = sorted[index] - mean;
                varianceSum += delta * delta;
            }

            return new LatencySummary(
                sorted.Length,
                sorted[0],
                sorted[sorted.Length - 1],
                mean,
                PercentileNearestRank(sorted, 0.5f),
                PercentileNearestRank(sorted, 0.95f),
                Mathf.Sqrt(varianceSum / sorted.Length));
        }

        private static float PercentileNearestRank(IReadOnlyList<float> sorted, float percentile)
        {
            int rank = Mathf.CeilToInt(percentile * sorted.Count);
            int index = Mathf.Clamp(rank - 1, 0, sorted.Count - 1);
            return sorted[index];
        }

#if UNITY_EDITOR
        private void OnValidate()
        {
            flushIntervalSeconds = Mathf.Max(0.1f, flushIntervalSeconds);
            maxEventsPerFrame = Mathf.Max(1, maxEventsPerFrame);
            maxQueuedEvents = Mathf.Max(1, maxQueuedEvents);
        }
#endif
    }
}
