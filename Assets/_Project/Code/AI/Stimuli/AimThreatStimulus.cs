using System;
using UnityEngine;

namespace QuickDraw.AI.Stimuli
{
    [Serializable]
    public struct AimThreatStimulus
    {
        public int SourceId;
        public Vector3 Origin;
        public Vector3 Direction;
        public float Timestamp;
        public float MaxDistance;
        public bool IsAiming;

        public AimThreatStimulus(
            int sourceId,
            Vector3 origin,
            Vector3 direction,
            float timestamp,
            float maxDistance,
            bool isAiming)
        {
            SourceId = sourceId;
            Origin = origin;
            Direction = direction;
            Timestamp = timestamp;
            MaxDistance = maxDistance;
            IsAiming = isAiming;
        }
    }
}

