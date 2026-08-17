using System;
using QuickDraw.Research.Actuation;
using Unity.MLAgents;
using Unity.MLAgents.Actuators;
using Unity.MLAgents.Sensors;
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
        }

        public override void OnEpisodeBegin()
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
    }
}
