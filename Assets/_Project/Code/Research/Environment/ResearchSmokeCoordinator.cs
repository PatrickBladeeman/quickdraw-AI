using System;
using System.Collections.Generic;
using Unity.MLAgents.SideChannels;
using UnityEngine;

namespace QuickDraw.Research.Environment
{
    public readonly struct ResearchSmokeEpisodeConfig
    {
        public ResearchSmokeEpisodeConfig(
            int episodeId,
            int seed,
            int decisionLimit,
            string expectedEnd)
        {
            EpisodeId = episodeId;
            Seed = seed;
            DecisionLimit = decisionLimit;
            ExpectedEnd = expectedEnd;
        }

        public int EpisodeId { get; }
        public int Seed { get; }
        public int DecisionLimit { get; }
        public string ExpectedEnd { get; }
    }

    [DefaultExecutionOrder(-1000)]
    [DisallowMultipleComponent]
    public sealed class ResearchSmokeCoordinator : MonoBehaviour
    {
        public const string UnityPackageVersion = "4.0.0";
        public const string ContractSha256 =
            "b6777d7a3b45a8134358c5946c9284c37c3414aad85c8e763dbdf0faf9e33523";

        [SerializeField] private ResearchSmokeAgent agent;

        private readonly Queue<ResearchSmokeEpisodeConfig> _episodeConfigs =
            new Queue<ResearchSmokeEpisodeConfig>();
        private readonly HashSet<int> _configuredEpisodeIds = new HashSet<int>();
        private readonly Dictionary<int, int> _outgoingSequences =
            new Dictionary<int, int>();

        private ResearchSideChannel _sideChannel;
        private bool _sideChannelRegistered;
        private bool _runConfigured;
        private string _runId = string.Empty;
        private int _lastConfiguredEpisodeId;
        private int _lastStartedEpisodeId;

        public ResearchSmokeAgent Agent => agent;
        public string RunId => _runId;
        public bool IsRunConfigured => _runConfigured;

        private void Awake()
        {
            _sideChannel = new ResearchSideChannel(HandleIncomingJson);
            SideChannelManager.RegisterSideChannel(_sideChannel);
            _sideChannelRegistered = true;
        }

        private void OnDestroy()
        {
            if (_sideChannelRegistered)
            {
                SideChannelManager.UnregisterSideChannel(_sideChannel);
                _sideChannelRegistered = false;
            }
        }

        public bool TryTakeNextEpisode(out ResearchSmokeEpisodeConfig config)
        {
            if (!_runConfigured || _episodeConfigs.Count == 0)
            {
                config = default;
                return false;
            }

            config = _episodeConfigs.Dequeue();
            if (config.EpisodeId <= _lastStartedEpisodeId)
            {
                SendInfrastructureError(
                    config.EpisodeId,
                    "Episode configuration is duplicate, stale, or out of order.");
                config = default;
                return false;
            }

            _lastStartedEpisodeId = config.EpisodeId;
            return true;
        }

        public void NotifyEpisodeStarted(
            ResearchSmokeEpisodeConfig config,
            int target)
        {
            Send(
                ResearchSmokeProtocol.EpisodeStarted,
                config.EpisodeId,
                new ResearchSmokePayload
                {
                    Seed = config.Seed,
                    DecisionLimit = config.DecisionLimit,
                    ExpectedEnd = config.ExpectedEnd,
                    Target = target
                });
        }

        public void NotifyEpisodeEnded(
            ResearchSmokeEpisodeConfig config,
            ResearchSmokeStepResult result,
            int stepCount)
        {
            Send(
                ResearchSmokeProtocol.EpisodeEnded,
                config.EpisodeId,
                new ResearchSmokePayload
                {
                    Seed = config.Seed,
                    ExpectedEnd = config.ExpectedEnd,
                    StepCount = stepCount,
                    Reason = result.Reason,
                    Interrupted = result.EndKind == ResearchSmokeEndKind.Truncated
                });
        }

        private void HandleIncomingJson(string json)
        {
            if (!ResearchSmokeProtocol.TryDeserialize(
                    json,
                    out ResearchSmokeEnvelope envelope,
                    out string error))
            {
                SendInfrastructureError(0, error);
                return;
            }

            switch (envelope.MessageType)
            {
                case ResearchSmokeProtocol.ConfigureRun:
                    HandleConfigureRun(envelope);
                    break;
                case ResearchSmokeProtocol.ConfigureEpisode:
                    HandleConfigureEpisode(envelope);
                    break;
                default:
                    SendInfrastructureError(
                        envelope.EpisodeId,
                        $"Unsupported Python-to-Unity message '{envelope.MessageType}'.");
                    break;
            }
        }

        private void HandleConfigureRun(ResearchSmokeEnvelope envelope)
        {
            if (_runConfigured || envelope.EpisodeId != 0 || envelope.Sequence != 1)
            {
                SendInfrastructureError(
                    envelope.EpisodeId,
                    "configure_run must be the first run message with episode 0 and sequence 1.");
                return;
            }

            if (!string.Equals(
                    envelope.Payload.ContractSha256,
                    ContractSha256,
                    StringComparison.Ordinal))
            {
                SendInfrastructureError(
                    0,
                    "The Python and Unity research-contract hashes do not match.");
                return;
            }

            _runId = envelope.RunId;
            _runConfigured = true;
            Send(
                ResearchSmokeProtocol.RunReady,
                0,
                new ResearchSmokePayload
                {
                    ContractSha256 = ContractSha256,
                    UnityPackageVersion = UnityPackageVersion,
                    ObservationSize = ResearchSmokeEpisode.ObservationSize,
                    DiscreteBranches = new[]
                    {
                        ResearchSmokeEpisode.MovementBranchSize,
                        ResearchSmokeEpisode.SubmitBranchSize
                    }
                });
        }

        private void HandleConfigureEpisode(ResearchSmokeEnvelope envelope)
        {
            if (!_runConfigured ||
                !string.Equals(envelope.RunId, _runId, StringComparison.Ordinal))
            {
                SendInfrastructureError(
                    envelope.EpisodeId,
                    "configure_episode does not match an active configured run.");
                return;
            }

            if (envelope.EpisodeId != _lastConfiguredEpisodeId + 1 ||
                envelope.EpisodeId <= _lastStartedEpisodeId ||
                envelope.Sequence != 1 ||
                !_configuredEpisodeIds.Add(envelope.EpisodeId))
            {
                SendInfrastructureError(
                    envelope.EpisodeId,
                    "Episode configuration is duplicate, stale, or out of order.");
                return;
            }

            ResearchSmokePayload payload = envelope.Payload;
            if (!payload.Seed.HasValue ||
                payload.Seed.Value < 0 ||
                !payload.DecisionLimit.HasValue ||
                payload.DecisionLimit.Value <= 0 ||
                payload.DecisionLimit.Value > 32 ||
                (payload.ExpectedEnd != ResearchSmokeEpisode.TerminalMode &&
                 payload.ExpectedEnd != ResearchSmokeEpisode.TruncationMode))
            {
                SendInfrastructureError(
                    envelope.EpisodeId,
                    "Episode seed, decision limit, or expected end is invalid.");
                return;
            }

            _episodeConfigs.Enqueue(
                new ResearchSmokeEpisodeConfig(
                    envelope.EpisodeId,
                    payload.Seed.Value,
                    payload.DecisionLimit.Value,
                    payload.ExpectedEnd));
            _lastConfiguredEpisodeId = envelope.EpisodeId;
        }

        private void SendInfrastructureError(int episodeId, string reason)
        {
            Debug.LogError($"Research smoke infrastructure error: {reason}");
            if (_sideChannel == null)
            {
                return;
            }

            Send(
                ResearchSmokeProtocol.InfrastructureError,
                Math.Max(0, episodeId),
                new ResearchSmokePayload { Reason = reason });
        }

        private void Send(
            string messageType,
            int episodeId,
            ResearchSmokePayload payload)
        {
            if (!_outgoingSequences.TryGetValue(episodeId, out int sequence))
            {
                sequence = 0;
            }

            sequence++;
            _outgoingSequences[episodeId] = sequence;
            _sideChannel.Send(
                ResearchSmokeProtocol.Serialize(
                    new ResearchSmokeEnvelope
                    {
                        SchemaVersion = ResearchSmokeProtocol.SchemaVersion,
                        MessageType = messageType,
                        RunId = string.IsNullOrEmpty(_runId) ? "unconfigured" : _runId,
                        EpisodeId = episodeId,
                        Sequence = sequence,
                        Payload = payload
                    }));
        }

        private sealed class ResearchSideChannel : SideChannel
        {
            private readonly Action<string> _onMessage;

            public ResearchSideChannel(Action<string> onMessage)
            {
                ChannelId = new Guid(ResearchSmokeProtocol.ChannelUuid);
                _onMessage = onMessage ?? throw new ArgumentNullException(nameof(onMessage));
            }

            protected override void OnMessageReceived(IncomingMessage message)
            {
                _onMessage(message.ReadString(string.Empty));
            }

            public void Send(string json)
            {
                using (var message = new OutgoingMessage())
                {
                    message.WriteString(json);
                    QueueMessageToSend(message);
                }
            }
        }
    }
}
