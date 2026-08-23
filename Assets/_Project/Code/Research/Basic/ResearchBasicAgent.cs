using System;
using QuickDraw.Research.Actuation;
using Unity.MLAgents;
using Unity.MLAgents.Actuators;
using Unity.MLAgents.Sensors;
using Unity.MLAgents.SideChannels;
using UnityEngine;

namespace QuickDraw.Research.Basic
{
    [DisallowMultipleComponent]
    public sealed class ResearchBasicAgent : Agent
    {
        [SerializeField] private ResearchBasicActuator actuator;
        [SerializeField] private ResearchBasicTarget target;
        [SerializeField] private ResearchBasicVisualSensorComponent visualSensor;
        [SerializeField] private int scenarioSeed = ResearchBasicContract.ScenarioSeed;

        private readonly ResearchBasicEpisode _episode = new ResearchBasicEpisode();
        private int _nextEpisodeIndex;
        private TruncationMaskSideChannel _truncationMaskSideChannel;

        public ResearchBasicActuator Actuator => actuator;
        public ResearchBasicTarget Target => target;
        public ResearchBasicVisualSensorComponent VisualSensor => visualSensor;
        public ResearchBasicEpisode Episode => _episode;
        public int ScenarioSeed => scenarioSeed;
        public int NextEpisodeIndex => _nextEpisodeIndex;
        public ResearchBasicStepResult LastCompletedResult { get; private set; }

        public override void Initialize()
        {
            if (actuator == null || target == null || visualSensor == null)
            {
                throw new InvalidOperationException(
                    "ResearchBasicAgent requires its actuator, target, and visual sensor.");
            }

            if (scenarioSeed < 0)
            {
                throw new InvalidOperationException("Scenario seed must be non-negative.");
            }

            actuator.ValidateConfiguration();
            MaxStep = 0;
            _truncationMaskSideChannel ??= new TruncationMaskSideChannel();
        }

        private void OnDestroy()
        {
            _truncationMaskSideChannel?.Dispose();
            _truncationMaskSideChannel = null;
        }

        public override void OnEpisodeBegin()
        {
            BeginEpisode();
        }

        internal void RecoverFromMissingVisualSensorReset()
        {
            BeginEpisode();
        }

        private void BeginEpisode()
        {
            _episode.Reset(scenarioSeed, _nextEpisodeIndex);
            _nextEpisodeIndex++;
            target.SetSlot(_episode.TargetSlot);
            actuator.ResetToSlot(_episode.PositionSlot);
            Physics.SyncTransforms();
            visualSensor.PrimeStackFromCurrentFrame();
        }

        public override void CollectObservations(VectorSensor sensor)
        {
        }

        public override void WriteDiscreteActionMask(IDiscreteActionMask actionMask)
        {
            for (int action = 0;
                 action < ResearchBasicContract.MovementBranchSize;
                 action++)
            {
                actionMask.SetActionEnabled(
                    0,
                    action,
                    _episode.IsActionEnabled(0, action));
            }
        }

        public override void OnActionReceived(ActionBuffers actions)
        {
            if (!_episode.IsActive)
            {
                SetReward(0f);
                return;
            }

            if (!ResearchBasicContract.IsPolicyDecisionStep(
                    Academy.Instance.StepCount))
            {
                return;
            }

            try
            {
                ResearchActionTuple action = ResearchBasicContract.MapAction(
                    actions.DiscreteActions[0],
                    actions.DiscreteActions[1],
                    _episode.DecisionCount);
                int nextPosition = _episode.PreviewPosition(action.Movement);
                ResearchBasicActuationResult actuation = actuator.Apply(
                    action,
                    nextPosition);
                ResearchBasicStepResult result = _episode.Step(
                    action,
                    actuation.Hit);
                SetReward(result.Reward);

                if (result.EndKind == ResearchBasicEndKind.None)
                {
                    return;
                }

                LastCompletedResult = result;
                if (result.EndKind == ResearchBasicEndKind.Truncated)
                {
                    _truncationMaskSideChannel.Send(_episode);
                    EpisodeInterrupted();
                }
                else
                {
                    EndEpisode();
                }
            }
            catch (Exception exception)
            {
                Debug.LogException(exception, this);
                SetReward(0f);
                LastCompletedResult = new ResearchBasicStepResult(
                    0f,
                    _episode.CumulativeReward,
                    ResearchBasicEndKind.InfrastructureInvalid,
                    ResearchBasicContract.InfrastructureInvalidReason,
                    _episode.PositionSlot,
                    false,
                    false,
                    _episode.DecisionCount);
                EpisodeInterrupted();
            }
        }

        public override void Heuristic(in ActionBuffers actionsOut)
        {
            ActionSegment<int> discrete = actionsOut.DiscreteActions;
            discrete[0] = 0;
            discrete[1] = 0;
        }

        private sealed class TruncationMaskSideChannel : SideChannel, IDisposable
        {
            private bool _registered;

            public TruncationMaskSideChannel()
            {
                ChannelId = new Guid(ResearchBasicContract.TruncationMaskChannelUuid);
                SideChannelManager.RegisterSideChannel(this);
                _registered = true;
            }

            protected override void OnMessageReceived(IncomingMessage message)
            {
                throw new InvalidOperationException(
                    "The Basic truncation-mask channel is Unity-to-Python only.");
            }

            public void Send(ResearchBasicEpisode episode)
            {
                if (episode == null)
                {
                    throw new ArgumentNullException(nameof(episode));
                }

                if (episode.IsActive ||
                    episode.DecisionCount != ResearchBasicContract.DecisionLimit)
                {
                    throw new InvalidOperationException(
                        "A truncation mask may be sent only from the final decision-limit state.");
                }

                var payload = new TruncationMaskMessage
                {
                    schema_version = ResearchBasicContract.TruncationMaskSchemaVersion,
                    message_type = ResearchBasicContract.TruncationMaskMessageType,
                    scenario_seed = episode.ScenarioSeed,
                    episode_index = episode.EpisodeIndex,
                    decision_count = episode.DecisionCount,
                    reason = ResearchBasicContract.DecisionLimitReason,
                    position_slot = episode.PositionSlot,
                    movement_unavailable = CreateUnavailableMask(
                        episode,
                        0,
                        ResearchBasicContract.MovementBranchSize),
                    combat_unavailable = CreateUnavailableMask(
                        episode,
                        1,
                        ResearchBasicContract.CombatBranchSize)
                };

                using (var message = new OutgoingMessage())
                {
                    message.WriteString(JsonUtility.ToJson(payload));
                    QueueMessageToSend(message);
                }
            }

            public void Dispose()
            {
                if (!_registered)
                {
                    return;
                }

                SideChannelManager.UnregisterSideChannel(this);
                _registered = false;
            }

            private static bool[] CreateUnavailableMask(
                ResearchBasicEpisode episode,
                int branch,
                int branchSize)
            {
                var result = new bool[branchSize];
                for (int action = 0; action < branchSize; action++)
                {
                    result[action] =
                        !episode.IsActionEnabledForContinuation(branch, action);
                }

                return result;
            }

            [Serializable]
            private sealed class TruncationMaskMessage
            {
                public string schema_version;
                public string message_type;
                public int scenario_seed;
                public int episode_index;
                public int decision_count;
                public string reason;
                public int position_slot;
                public bool[] movement_unavailable;
                public bool[] combat_unavailable;
            }
        }
    }
}
