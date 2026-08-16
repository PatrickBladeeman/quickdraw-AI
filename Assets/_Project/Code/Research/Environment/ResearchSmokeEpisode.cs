using System;

namespace QuickDraw.Research.Environment
{
    public enum ResearchSmokeEndKind
    {
        None,
        Terminal,
        Truncated
    }

    public readonly struct ResearchSmokeStepResult
    {
        public ResearchSmokeStepResult(
            float reward,
            ResearchSmokeEndKind endKind,
            string reason)
        {
            Reward = reward;
            EndKind = endKind;
            Reason = reason;
        }

        public float Reward { get; }
        public ResearchSmokeEndKind EndKind { get; }
        public string Reason { get; }
    }

    public sealed class ResearchSmokeEpisode
    {
        public const int ObservationSize = 4;
        public const int MovementBranchSize = 3;
        public const int SubmitBranchSize = 2;
        public const string TerminalMode = "terminal";
        public const string TruncationMode = "truncation";
        public const string GoalReason = "smoke_goal";
        public const string DecisionLimitReason = "decision_limit";

        private const int MinimumPosition = -1;
        private const int MaximumPosition = 1;
        private const int SeedObservationModulus = 997;

        public int EpisodeId { get; private set; }
        public int Seed { get; private set; }
        public int DecisionLimit { get; private set; }
        public string ExpectedEnd { get; private set; } = string.Empty;
        public int Position { get; private set; }
        public int Target { get; private set; }
        public int StepCount { get; private set; }
        public bool IsActive { get; private set; }

        public void Reset(
            int episodeId,
            int seed,
            int decisionLimit,
            string expectedEnd)
        {
            if (episodeId <= 0)
            {
                throw new ArgumentOutOfRangeException(nameof(episodeId));
            }

            if (seed < 0)
            {
                throw new ArgumentOutOfRangeException(nameof(seed));
            }

            if (decisionLimit <= 0)
            {
                throw new ArgumentOutOfRangeException(nameof(decisionLimit));
            }

            if (expectedEnd != TerminalMode && expectedEnd != TruncationMode)
            {
                throw new ArgumentException(
                    $"Expected end must be '{TerminalMode}' or '{TruncationMode}'.",
                    nameof(expectedEnd));
            }

            EpisodeId = episodeId;
            Seed = seed;
            DecisionLimit = decisionLimit;
            ExpectedEnd = expectedEnd;
            Position = 0;
            Target = SampleTarget(seed);
            StepCount = 0;
            IsActive = true;
        }

        public float[] CreateObservation()
        {
            if (!IsActive)
            {
                return new float[ObservationSize];
            }

            return new[]
            {
                (float)Position,
                (float)Target,
                StepCount / (float)DecisionLimit,
                (Seed % SeedObservationModulus) / (float)(SeedObservationModulus - 1)
            };
        }

        public bool IsActionEnabled(int branch, int action)
        {
            if (!IsActive)
            {
                return action == 0;
            }

            if (branch == 0)
            {
                return action switch
                {
                    0 => true,
                    1 => Position > MinimumPosition,
                    2 => Position < MaximumPosition,
                    _ => false
                };
            }

            if (branch == 1)
            {
                return action switch
                {
                    0 => true,
                    1 => ExpectedEnd == TerminalMode,
                    _ => false
                };
            }

            return false;
        }

        public ResearchSmokeStepResult Step(int movementAction, int submitAction)
        {
            if (!IsActive)
            {
                throw new InvalidOperationException("The smoke episode is not active.");
            }

            if (!IsActionEnabled(0, movementAction))
            {
                throw new ArgumentOutOfRangeException(
                    nameof(movementAction),
                    movementAction,
                    "The movement action is outside the branch or mechanically masked.");
            }

            if (!IsActionEnabled(1, submitAction))
            {
                throw new ArgumentOutOfRangeException(
                    nameof(submitAction),
                    submitAction,
                    "The submit action is outside the branch or mechanically masked.");
            }

            if (movementAction == 1)
            {
                Position--;
            }
            else if (movementAction == 2)
            {
                Position++;
            }

            StepCount++;
            float reward = -0.01f;

            if (submitAction == 1)
            {
                if (Position == Target)
                {
                    IsActive = false;
                    return new ResearchSmokeStepResult(
                        reward + 1f,
                        ResearchSmokeEndKind.Terminal,
                        GoalReason);
                }

                reward -= 0.02f;
            }

            if (StepCount >= DecisionLimit)
            {
                IsActive = false;
                return new ResearchSmokeStepResult(
                    reward,
                    ResearchSmokeEndKind.Truncated,
                    DecisionLimitReason);
            }

            return new ResearchSmokeStepResult(
                reward,
                ResearchSmokeEndKind.None,
                string.Empty);
        }

        private static int SampleTarget(int seed)
        {
            unchecked
            {
                uint value = (uint)seed;
                value ^= 0x9E3779B9u;
                value ^= value >> 16;
                value *= 0x7FEB352Du;
                value ^= value >> 15;
                value *= 0x846CA68Bu;
                value ^= value >> 16;
                return (int)(value % 3u) - 1;
            }
        }
    }
}
