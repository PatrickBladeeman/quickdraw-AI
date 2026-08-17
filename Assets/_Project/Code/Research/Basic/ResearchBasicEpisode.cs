using System;
using QuickDraw.Research.Actuation;

namespace QuickDraw.Research.Basic
{
    public enum ResearchBasicEndKind
    {
        None,
        Terminal,
        Truncated,
        InfrastructureInvalid
    }

    public readonly struct ResearchBasicStepResult
    {
        public ResearchBasicStepResult(
            float reward,
            float cumulativeReward,
            ResearchBasicEndKind endKind,
            string reason,
            int positionSlot,
            bool shotFired,
            bool hit,
            int decisionCount)
        {
            Reward = reward;
            CumulativeReward = cumulativeReward;
            EndKind = endKind;
            Reason = reason;
            PositionSlot = positionSlot;
            ShotFired = shotFired;
            Hit = hit;
            DecisionCount = decisionCount;
        }

        public float Reward { get; }
        public float CumulativeReward { get; }
        public ResearchBasicEndKind EndKind { get; }
        public string Reason { get; }
        public int PositionSlot { get; }
        public bool ShotFired { get; }
        public bool Hit { get; }
        public int DecisionCount { get; }
    }

    public sealed class ResearchBasicEpisode
    {
        public int ScenarioSeed { get; private set; }
        public int EpisodeIndex { get; private set; }
        public int PositionSlot { get; private set; }
        public int TargetSlot { get; private set; }
        public int DecisionCount { get; private set; }
        public int ShotsFired { get; private set; }
        public int Misses { get; private set; }
        public int RemainingAmmunition { get; private set; }
        public int CooldownDecisionsRemaining { get; private set; }
        public float CumulativeReward { get; private set; }
        public bool IsActive { get; private set; }

        public void Reset(int scenarioSeed, int episodeIndex)
        {
            if (scenarioSeed < 0)
            {
                throw new ArgumentOutOfRangeException(nameof(scenarioSeed));
            }

            if (episodeIndex < 0)
            {
                throw new ArgumentOutOfRangeException(nameof(episodeIndex));
            }

            ScenarioSeed = scenarioSeed;
            EpisodeIndex = episodeIndex;
            PositionSlot = 0;
            TargetSlot = SampleTargetSlot(scenarioSeed, episodeIndex);
            DecisionCount = 0;
            ShotsFired = 0;
            Misses = 0;
            RemainingAmmunition = ResearchBasicContract.AmmunitionCapacity;
            CooldownDecisionsRemaining = 0;
            CumulativeReward = 0f;
            IsActive = true;
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
                    1 => PositionSlot > ResearchBasicContract.MinimumSlot,
                    2 => PositionSlot < ResearchBasicContract.MaximumSlot,
                    _ => false
                };
            }

            if (branch == 1)
            {
                return action is 0 or 1;
            }

            return false;
        }

        public int PreviewPosition(ResearchMovementIntent movement)
        {
            if (!IsActive)
            {
                throw new InvalidOperationException("The Basic episode is not active.");
            }

            int movementBranch = ResearchBasicContract.ToMovementBranch(movement);
            if (!IsActionEnabled(0, movementBranch))
            {
                throw new ArgumentOutOfRangeException(
                    nameof(movement),
                    movement,
                    "The movement is mechanically unavailable.");
            }

            return movement switch
            {
                ResearchMovementIntent.Left => PositionSlot - 1,
                ResearchMovementIntent.Right => PositionSlot + 1,
                _ => PositionSlot
            };
        }

        public ResearchBasicStepResult Step(
            ResearchActionTuple action,
            bool physicalHit)
        {
            if (!IsActive)
            {
                throw new InvalidOperationException("The Basic episode is not active.");
            }

            if (action.DecisionStep != DecisionCount)
            {
                throw new InvalidOperationException(
                    $"Action decision step {action.DecisionStep} does not match " +
                    $"episode step {DecisionCount}.");
            }

            if (action.Utility != ResearchUtilityIntent.Idle)
            {
                throw new ArgumentOutOfRangeException(
                    nameof(action),
                    "Basic fixes the utility intent to Idle.");
            }

            int nextPosition = PreviewPosition(action.Movement);
            bool shotFired = action.Combat == ResearchCombatIntent.Shoot;
            bool expectedHit = shotFired && nextPosition == TargetSlot;
            if (physicalHit != expectedHit)
            {
                throw new InvalidOperationException(
                    "Physical hitscan result disagrees with the registered slot geometry.");
            }

            PositionSlot = nextPosition;
            DecisionCount++;
            float reward = ResearchBasicContract.PerDecisionReward;

            if (shotFired)
            {
                if (CooldownDecisionsRemaining > 0 || RemainingAmmunition <= 0)
                {
                    throw new InvalidOperationException(
                        "A shot was accepted while the weapon was mechanically unavailable.");
                }

                RemainingAmmunition--;
                ShotsFired++;
                if (physicalHit)
                {
                    reward += ResearchBasicContract.HitReward;
                }
                else
                {
                    Misses++;
                    reward += ResearchBasicContract.MissReward;
                }
            }

            CooldownDecisionsRemaining = ResearchBasicContract.ShotCooldownDecisions;

            CumulativeReward += reward;

            if (physicalHit)
            {
                IsActive = false;
                return CreateResult(
                    reward,
                    ResearchBasicEndKind.Terminal,
                    ResearchBasicContract.TargetHitReason,
                    shotFired,
                    true);
            }

            if (DecisionCount >= ResearchBasicContract.DecisionLimit)
            {
                IsActive = false;
                return CreateResult(
                    reward,
                    ResearchBasicEndKind.Truncated,
                    ResearchBasicContract.DecisionLimitReason,
                    shotFired,
                    false);
            }

            return CreateResult(
                reward,
                ResearchBasicEndKind.None,
                string.Empty,
                shotFired,
                false);
        }

        public static int SampleTargetSlot(int scenarioSeed, int episodeIndex)
        {
            if (scenarioSeed < 0)
            {
                throw new ArgumentOutOfRangeException(nameof(scenarioSeed));
            }

            if (episodeIndex < 0)
            {
                throw new ArgumentOutOfRangeException(nameof(episodeIndex));
            }

            unchecked
            {
                uint value = (uint)scenarioSeed;
                value ^= ((uint)episodeIndex + 1u) * 0x9E3779B9u;
                value ^= value >> 16;
                value *= 0x7FEB352Du;
                value ^= value >> 15;
                value *= 0x846CA68Bu;
                value ^= value >> 16;
                uint slotCount = (uint)(
                    ResearchBasicContract.MaximumSlot -
                    ResearchBasicContract.MinimumSlot + 1);
                return (int)(value % slotCount) + ResearchBasicContract.MinimumSlot;
            }
        }

        private ResearchBasicStepResult CreateResult(
            float reward,
            ResearchBasicEndKind endKind,
            string reason,
            bool shotFired,
            bool hit)
        {
            return new ResearchBasicStepResult(
                reward,
                CumulativeReward,
                endKind,
                reason,
                PositionSlot,
                shotFired,
                hit,
                DecisionCount);
        }
    }
}
