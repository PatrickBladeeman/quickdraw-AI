using System;
using Unity.MLAgents;
using Unity.MLAgents.Actuators;
using Unity.MLAgents.Sensors;
using UnityEngine;

namespace QuickDraw.Research.Environment
{
    [DisallowMultipleComponent]
    public sealed class ResearchSmokeAgent : Agent
    {
        [SerializeField] private ResearchSmokeCoordinator coordinator;

        private readonly ResearchSmokeEpisode _episode = new ResearchSmokeEpisode();
        private ResearchSmokeEpisodeConfig _config;

        public ResearchSmokeCoordinator Coordinator => coordinator;
        public ResearchSmokeEpisode Episode => _episode;

        public override void Initialize()
        {
            if (coordinator == null)
            {
                throw new InvalidOperationException(
                    "ResearchSmokeAgent requires an explicitly wired coordinator.");
            }

            MaxStep = 0;
        }

        public override void OnEpisodeBegin()
        {
            if (!coordinator.TryTakeNextEpisode(out _config))
            {
                return;
            }

            _episode.Reset(
                _config.EpisodeId,
                _config.Seed,
                _config.DecisionLimit,
                _config.ExpectedEnd);
            coordinator.NotifyEpisodeStarted(_config, _episode.Target);
        }

        public override void CollectObservations(VectorSensor sensor)
        {
            float[] observation = _episode.CreateObservation();
            for (int index = 0; index < observation.Length; index++)
            {
                sensor.AddObservation(observation[index]);
            }
        }

        public override void WriteDiscreteActionMask(IDiscreteActionMask actionMask)
        {
            for (int action = 0; action < ResearchSmokeEpisode.MovementBranchSize; action++)
            {
                actionMask.SetActionEnabled(
                    0,
                    action,
                    _episode.IsActionEnabled(0, action));
            }

            for (int action = 0; action < ResearchSmokeEpisode.SubmitBranchSize; action++)
            {
                actionMask.SetActionEnabled(
                    1,
                    action,
                    _episode.IsActionEnabled(1, action));
            }
        }

        public override void OnActionReceived(ActionBuffers actions)
        {
            if (!_episode.IsActive)
            {
                SetReward(0f);
                return;
            }

            try
            {
                ResearchSmokeStepResult result = _episode.Step(
                    actions.DiscreteActions[0],
                    actions.DiscreteActions[1]);
                SetReward(result.Reward);

                if (result.EndKind == ResearchSmokeEndKind.None)
                {
                    return;
                }

                coordinator.NotifyEpisodeEnded(
                    _config,
                    result,
                    _episode.StepCount);

                if (result.EndKind == ResearchSmokeEndKind.Truncated)
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
                EpisodeInterrupted();
            }
        }

        public override void Heuristic(in ActionBuffers actionsOut)
        {
            ActionSegment<int> discreteActions = actionsOut.DiscreteActions;
            discreteActions[0] = 0;
            discreteActions[1] = 0;
        }
    }
}
