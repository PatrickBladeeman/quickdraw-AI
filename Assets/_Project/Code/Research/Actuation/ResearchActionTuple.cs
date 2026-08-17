using System;

namespace QuickDraw.Research.Actuation
{
    public enum ResearchMovementIntent
    {
        Stay = 0,
        Forward = 1,
        Backward = 2,
        Left = 3,
        Right = 4
    }

    public enum ResearchCombatIntent
    {
        Idle = 0,
        Shoot = 1
    }

    public enum ResearchUtilityIntent
    {
        Idle = 0,
        Reload = 1,
        Interact = 2
    }

    public readonly struct ResearchActionTuple : IEquatable<ResearchActionTuple>
    {
        public ResearchActionTuple(
            ResearchMovementIntent movement,
            ResearchCombatIntent combat,
            ResearchUtilityIntent utility,
            int decisionStep)
        {
            if (decisionStep < 0)
            {
                throw new ArgumentOutOfRangeException(nameof(decisionStep));
            }

            Movement = movement;
            Combat = combat;
            Utility = utility;
            DecisionStep = decisionStep;
        }

        public ResearchMovementIntent Movement { get; }
        public ResearchCombatIntent Combat { get; }
        public ResearchUtilityIntent Utility { get; }
        public int DecisionStep { get; }

        public bool Equals(ResearchActionTuple other)
        {
            return Movement == other.Movement &&
                   Combat == other.Combat &&
                   Utility == other.Utility &&
                   DecisionStep == other.DecisionStep;
        }

        public override bool Equals(object obj)
        {
            return obj is ResearchActionTuple other && Equals(other);
        }

        public override int GetHashCode()
        {
            unchecked
            {
                int hash = 17;
                hash = hash * 31 + (int)Movement;
                hash = hash * 31 + (int)Combat;
                hash = hash * 31 + (int)Utility;
                hash = hash * 31 + DecisionStep;
                return hash;
            }
        }
    }
}
