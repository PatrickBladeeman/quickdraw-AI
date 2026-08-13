using System;
using UnityEngine;

namespace QuickDraw.AI.Activity
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(CharacterController))]
    public sealed class PatrolActivity : MonoBehaviour
    {
        private const string PatrolName = "Patrol";

        [SerializeField] private Transform patrolPointA;
        [SerializeField] private Transform patrolPointB;
        [SerializeField, Min(0f)] private float moveSpeed = 1.5f;
        [SerializeField, Min(0f)] private float arrivalTolerance = 0.01f;
        [SerializeField] private bool startOnEnable = true;

        private Vector3 _resetPosition;
        private Quaternion _resetRotation;
        private float _legLength;
        private CharacterController _characterController;

        public string ActivityName => PatrolName;
        public bool IsRunning { get; private set; }
        public bool IsInterruptible => true;
        public bool IsInterrupted { get; private set; }
        public bool IsCancelled { get; private set; }
        public float StartTime { get; private set; } = -1f;
        public Transform CurrentTarget { get; private set; }
        public float Progress { get; private set; }
        public string InterruptionReason { get; private set; } = string.Empty;
        public float InterruptionTime { get; private set; } = -1f;
        public float ResumeTime { get; private set; } = -1f;

        public event Action<PatrolActivity> ActivityStarted;
        public event Action<PatrolActivity> ActivityInterrupted;
        public event Action<PatrolActivity> ActivityResumed;
        public event Action<PatrolActivity> ActivityCancelled;

        private void Awake()
        {
            _characterController = GetComponent<CharacterController>();
            _resetPosition = transform.position;
            _resetRotation = transform.rotation;
            SelectTarget(patrolPointA);
        }

        private void OnEnable()
        {
            if (startOnEnable)
            {
                StartActivity();
            }
        }

        private void Update()
        {
            TickActivity(Time.deltaTime);
        }

        [ContextMenu("Start Activity")]
        public void StartActivity()
        {
            if (IsRunning || patrolPointA == null || patrolPointB == null)
            {
                return;
            }

            if (CurrentTarget == null)
            {
                SelectTarget(patrolPointA);
            }

            IsRunning = true;
            IsInterrupted = false;
            IsCancelled = false;
            InterruptionReason = string.Empty;
            StartTime = Time.realtimeSinceStartup;
            ActivityStarted?.Invoke(this);
        }

        public void TickActivity(float deltaTime)
        {
            if (!IsRunning || CurrentTarget == null || deltaTime <= 0f || !_characterController.enabled)
            {
                return;
            }

            Vector3 targetPosition = GetGroundedTargetPosition(CurrentTarget);
            Vector3 nextPosition = Vector3.MoveTowards(
                transform.position,
                targetPosition,
                moveSpeed * deltaTime);
            _characterController.Move(nextPosition - transform.position);

            float remainingDistance = Vector3.Distance(transform.position, targetPosition);
            Progress = _legLength > Mathf.Epsilon
                ? Mathf.Clamp01(1f - remainingDistance / _legLength)
                : 1f;

            if (remainingDistance <= arrivalTolerance)
            {
                transform.position = targetPosition;
                SelectTarget(CurrentTarget == patrolPointA ? patrolPointB : patrolPointA);
            }
        }

        [ContextMenu("Interrupt Activity")]
        public void InterruptActivity()
        {
            InterruptActivity("Manual");
        }

        public void InterruptActivity(string reason)
        {
            if (!IsRunning)
            {
                return;
            }

            IsRunning = false;
            IsInterrupted = true;
            InterruptionReason = string.IsNullOrWhiteSpace(reason) ? "Unspecified" : reason;
            InterruptionTime = Time.realtimeSinceStartup;
            ActivityInterrupted?.Invoke(this);
        }

        [ContextMenu("Resume Activity")]
        public void ResumeActivity()
        {
            if (!IsInterrupted || IsCancelled)
            {
                return;
            }

            IsRunning = true;
            IsInterrupted = false;
            ResumeTime = Time.realtimeSinceStartup;
            ActivityResumed?.Invoke(this);
        }

        [ContextMenu("Cancel Activity")]
        public void CancelActivity()
        {
            if (IsCancelled && !IsRunning && !IsInterrupted)
            {
                return;
            }

            IsRunning = false;
            IsInterrupted = false;
            IsCancelled = true;
            ActivityCancelled?.Invoke(this);
        }

        [ContextMenu("Reset Activity")]
        public void ResetActivity()
        {
            bool controllerWasEnabled = _characterController.enabled;
            _characterController.enabled = false;
            transform.SetPositionAndRotation(_resetPosition, _resetRotation);
            _characterController.enabled = controllerWasEnabled;
            IsRunning = false;
            IsInterrupted = false;
            IsCancelled = false;
            StartTime = -1f;
            InterruptionReason = string.Empty;
            InterruptionTime = -1f;
            ResumeTime = -1f;
            SelectTarget(patrolPointA);

            if (startOnEnable)
            {
                StartActivity();
            }
        }

        private void SelectTarget(Transform target)
        {
            CurrentTarget = target;
            _legLength = target != null
                ? Vector3.Distance(transform.position, GetGroundedTargetPosition(target))
                : 0f;
            Progress = 0f;
        }

        private Vector3 GetGroundedTargetPosition(Transform target)
        {
            Vector3 targetPosition = target.position;
            targetPosition.y = transform.position.y;
            return targetPosition;
        }
    }
}
