using System;
using QuickDraw.Research.Actuation;
using UnityEngine;

namespace QuickDraw.Research.Basic
{
    public readonly struct ResearchBasicActuationResult
    {
        public ResearchBasicActuationResult(bool shotFired, bool hit)
        {
            ShotFired = shotFired;
            Hit = hit;
        }

        public bool ShotFired { get; }
        public bool Hit { get; }
    }

    [DisallowMultipleComponent]
    public sealed class ResearchBasicActuator : MonoBehaviour
    {
        [SerializeField] private Transform agentRoot;
        [SerializeField] private Camera observationCamera;
        [SerializeField] private ResearchBasicTarget target;
        [SerializeField] private LayerMask targetLayerMask;
        [SerializeField] private float hitscanDistance = 40f;

        private Vector3 _origin;
        private bool _initialized;

        public Transform AgentRoot => agentRoot;
        public Camera ObservationCamera => observationCamera;
        public ResearchBasicTarget Target => target;
        public LayerMask TargetLayerMask => targetLayerMask;
        public float HitscanDistance => hitscanDistance;

        public void ValidateConfiguration()
        {
            if (agentRoot == null || observationCamera == null || target == null)
            {
                throw new InvalidOperationException(
                    "ResearchBasicActuator requires an agent root, camera, and target.");
            }

            if (targetLayerMask.value == 0)
            {
                throw new InvalidOperationException(
                    "ResearchBasicActuator requires a non-empty target layer mask.");
            }

            if (hitscanDistance <= 0f)
            {
                throw new InvalidOperationException(
                    "ResearchBasicActuator hitscan distance must be positive.");
            }

            EnsureInitialized();
        }

        public void ResetToSlot(int slot)
        {
            ValidateSlot(slot);
            EnsureInitialized();
            SetPosition(slot);
        }

        public ResearchBasicActuationResult Apply(
            ResearchActionTuple action,
            int nextPositionSlot)
        {
            ValidateConfiguration();
            ValidateSlot(nextPositionSlot);
            SetPosition(nextPositionSlot);

            bool shotFired = action.Combat == ResearchCombatIntent.Shoot;
            if (!shotFired)
            {
                return new ResearchBasicActuationResult(false, false);
            }

            Ray ray = observationCamera.ViewportPointToRay(
                new Vector3(0.5f, 0.5f, 0f));
            bool hit = Physics.Raycast(
                ray,
                out RaycastHit hitInfo,
                hitscanDistance,
                targetLayerMask,
                QueryTriggerInteraction.Ignore) &&
                hitInfo.collider.GetComponentInParent<ResearchBasicTarget>() == target;
            return new ResearchBasicActuationResult(true, hit);
        }

        private void SetPosition(int slot)
        {
            agentRoot.position = _origin +
                Vector3.right * (slot * ResearchBasicContract.SlotSpacing);
            Physics.SyncTransforms();
        }

        private void EnsureInitialized()
        {
            if (_initialized)
            {
                return;
            }

            if (agentRoot == null)
            {
                throw new InvalidOperationException("Agent root is not configured.");
            }

            _origin = agentRoot.position;
            _initialized = true;
        }

        private static void ValidateSlot(int slot)
        {
            if (slot < ResearchBasicContract.MinimumSlot ||
                slot > ResearchBasicContract.MaximumSlot)
            {
                throw new ArgumentOutOfRangeException(nameof(slot));
            }
        }
    }
}
