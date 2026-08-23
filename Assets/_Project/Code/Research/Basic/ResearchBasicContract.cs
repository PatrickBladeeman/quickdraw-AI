using System;
using QuickDraw.Research.Actuation;

namespace QuickDraw.Research.Basic
{
    public static class ResearchBasicContract
    {
        public const string BehaviorName = "QuickDrawResearchBasic";
        public const string TraceSchemaVersion = "quickdraw.basic-baseline-trace.v1";
        public const string EpisodeSchemaVersion = "quickdraw.basic-episode.v1";
        public const string TargetHitReason = "target_hit";
        public const string DecisionLimitReason = "decision_limit";
        public const string InfrastructureInvalidReason = "infrastructure_invalid";
        public const string TruncationMaskSchemaVersion =
            "quickdraw.basic-truncation-mask.v1";
        public const string TruncationMaskMessageType = "truncation_mask";
        public const string TruncationMaskChannelUuid =
            "0541088f-93b9-4299-8c9e-af7431da553a";

        public const int ObservationWidth = 84;
        public const int ObservationHeight = 84;
        public const int ObservationStacks = 4;
        public const int MovementBranchSize = 3;
        public const int CombatBranchSize = 2;
        public const int DecisionLimit = 300;
        public const int DecisionPeriodFixedSteps = 5;
        public const int ScenarioSeed = 31001;
        public const int AmmunitionCapacity = DecisionLimit;
        public const int ShotCooldownDecisions = 0;
        public const int MinimumSlot = -4;
        public const int MaximumSlot = 4;
        public const float SlotSpacing = 0.75f;
        public const float PerDecisionReward = -0.01f;
        public const float HitReward = 1f;
        public const float MissReward = -0.02f;

        public static bool IsPolicyDecisionStep(int academyStepCount)
        {
            return academyStepCount % DecisionPeriodFixedSteps == 0;
        }

        public static ResearchActionTuple MapAction(
            int movementBranch,
            int combatBranch,
            int decisionStep)
        {
            ResearchMovementIntent movement = movementBranch switch
            {
                0 => ResearchMovementIntent.Stay,
                1 => ResearchMovementIntent.Left,
                2 => ResearchMovementIntent.Right,
                _ => throw new ArgumentOutOfRangeException(nameof(movementBranch))
            };

            ResearchCombatIntent combat = combatBranch switch
            {
                0 => ResearchCombatIntent.Idle,
                1 => ResearchCombatIntent.Shoot,
                _ => throw new ArgumentOutOfRangeException(nameof(combatBranch))
            };

            return new ResearchActionTuple(
                movement,
                combat,
                ResearchUtilityIntent.Idle,
                decisionStep);
        }

        public static int ToMovementBranch(ResearchMovementIntent movement)
        {
            return movement switch
            {
                ResearchMovementIntent.Stay => 0,
                ResearchMovementIntent.Left => 1,
                ResearchMovementIntent.Right => 2,
                _ => throw new ArgumentOutOfRangeException(nameof(movement))
            };
        }
    }
}
