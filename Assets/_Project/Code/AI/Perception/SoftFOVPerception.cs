using System;
using QuickDraw.AI.Stimuli;
using UnityEngine;

namespace QuickDraw.AI.Perception
{
    public enum PerceptionState
    {
        Idle,
        Suspicious,
        Orienting,
        ThreatConfirmed,
        Recovering
    }

    [DisallowMultipleComponent]
    [RequireComponent(typeof(CharacterController))]
    public sealed class SoftFOVPerception : MonoBehaviour
    {
        private const int LineOfSightHitCapacity = 16;
        private const float StateGizmoRadius = 0.18f;
        private const float StateGizmoClearance = 0.2f;
        private static readonly int BaseColorPropertyId = Shader.PropertyToID("_BaseColor");
        private static readonly int ColorPropertyId = Shader.PropertyToID("_Color");

        [Header("References")]
        [SerializeField] private Transform eye;
        [SerializeField] private AimThreatEmitter stimulusEmitter;
        [SerializeField] private Collider targetBounds;
        [SerializeField] private LayerMask occludersMask = Physics.DefaultRaycastLayers;

        [Header("Runtime State Visualization")]
        [SerializeField] private Renderer bodyRenderer;
        [SerializeField] private Renderer facingMarkerRenderer;

        [Header("Vision")]
        [SerializeField, Min(0f)] private float maxDistance = 20f;
        [SerializeField, Range(1f, 179f)] private float coreFOV = 90f;
        [SerializeField, Range(1f, 179f)] private float peripheralFOV = 140f;

        [Header("Suspicion")]
        [SerializeField, Min(0.01f)] private float suspicionBuildTime = 0.45f;
        [SerializeField, Min(0f)] private float suspicionDecayRate = 0.8f;
        [SerializeField, Range(0f, 1f)] private float suspicionEnterThreshold = 0.5f;
        [SerializeField, Range(0f, 1f)] private float suspicionExitThreshold = 0.3f;
        [SerializeField, Min(1f)] private float tickRateHz = 12f;

        [Header("Orientation")]
        [SerializeField, Min(0f)] private float turnYawSpeed = 300f;
        [SerializeField, Range(0.1f, 45f)] private float facingThreshold = 3f;

        private readonly RaycastHit[] _lineOfSightHits = new RaycastHit[LineOfSightHitCapacity];
        private AimThreatStimulus _currentStimulus;
        private float _lastTickTime;
        private float _nextTickTime;
        private bool _episodeArmed = true;
        private bool _releaseObserved = true;
        private bool _stimulusVisible;
        private MaterialPropertyBlock _statePropertyBlock;

        public PerceptionState State { get; private set; }
        public float Suspicion { get; private set; }
        public float LastDistance { get; private set; }
        public float LastAngle { get; private set; } = 180f;
        public float YawDifference { get; private set; } = 180f;
        public bool HasLineOfSight { get; private set; }
        public bool AimThreatensTarget { get; private set; }
        public int ThreatEpisodeId { get; private set; }
        public float LastConfirmationTime { get; private set; } = -1f;
        public AimThreatStimulus CurrentStimulus => _currentStimulus;

        public event Action<PerceptionState> StateChanged;
        public event Action<SoftFOVPerception> ThreatConfirmed;

        private void Awake()
        {
            ResolveReferences();
            ResetPerception();
        }

        private void OnEnable()
        {
            ResolveReferences();
            ApplyStateVisualization();
            _lastTickTime = Time.time;
            _nextTickTime = Time.time;
        }

        private void Update()
        {
            TickScheduler(Time.time);
            TickOrientation(Time.deltaTime);
        }

        [ContextMenu("Reset Perception")]
        public void ResetPerception()
        {
            Suspicion = 0f;
            LastDistance = 0f;
            LastAngle = 180f;
            YawDifference = 180f;
            HasLineOfSight = false;
            AimThreatensTarget = false;
            ThreatEpisodeId = 0;
            LastConfirmationTime = -1f;
            _currentStimulus = default;
            _episodeArmed = true;
            _releaseObserved = true;
            _stimulusVisible = false;
            SetState(PerceptionState.Idle);
        }

        private void TickScheduler(float currentTime)
        {
            if (currentTime < _nextTickTime)
            {
                return;
            }

            float elapsed = Mathf.Max(0f, currentTime - _lastTickTime);
            _lastTickTime = currentTime;
            _nextTickTime = currentTime + 1f / Mathf.Max(1f, tickRateHz);
            TickPerception(elapsed);
        }

        private void TickPerception(float elapsed)
        {
            ResolveReferences();
            _currentStimulus = stimulusEmitter != null
                ? stimulusEmitter.CurrentStimulus
                : default;

            if (!_currentStimulus.IsAiming)
            {
                _releaseObserved = true;
            }

            _stimulusVisible = EvaluateStimulus(_currentStimulus);

            if (!_episodeArmed)
            {
                UpdateConfirmedEpisode(elapsed);
                return;
            }

            if (_stimulusVisible)
            {
                if (State == PerceptionState.Idle || State == PerceptionState.Recovering)
                {
                    SetState(PerceptionState.Suspicious);
                }

                if (LastAngle <= coreFOV * 0.5f)
                {
                    Suspicion = 1f;
                }
                else
                {
                    float gainRate = suspicionEnterThreshold / Mathf.Max(0.01f, suspicionBuildTime);
                    Suspicion = Mathf.Clamp01(Suspicion + gainRate * Mathf.Max(0f, elapsed));
                }

                if (Suspicion >= suspicionEnterThreshold)
                {
                    SetState(PerceptionState.Orienting);
                }
                else if (State != PerceptionState.Orienting)
                {
                    SetState(PerceptionState.Suspicious);
                }

                return;
            }

            DecaySuspicion(elapsed);
            SetState(Suspicion <= suspicionExitThreshold
                ? PerceptionState.Idle
                : PerceptionState.Suspicious);
        }

        private void TickOrientation(float deltaTime)
        {
            bool canConfirm = State == PerceptionState.Orienting && _episodeArmed;
            bool canTrackConfirmedThreat =
                State == PerceptionState.ThreatConfirmed && !_episodeArmed;
            if ((!canConfirm && !canTrackConfirmedThreat) ||
                !_stimulusVisible ||
                deltaTime < 0f)
            {
                return;
            }

            AimThreatStimulus liveStimulus = stimulusEmitter != null
                ? stimulusEmitter.CurrentStimulus
                : default;
            float effectiveMaxDistance = GetEffectiveMaxDistance(liveStimulus);
            bool sameActiveStimulus = liveStimulus.IsAiming &&
                liveStimulus.SourceId == _currentStimulus.SourceId &&
                AimIntersectsTarget(liveStimulus, effectiveMaxDistance);
            if (!sameActiveStimulus)
            {
                return;
            }

            Vector3 toSource = liveStimulus.Origin - transform.position;
            toSource.y = 0f;
            if (toSource.sqrMagnitude <= Mathf.Epsilon)
            {
                return;
            }

            float targetYaw = Quaternion.LookRotation(toSource.normalized, Vector3.up).eulerAngles.y;
            float currentYaw = transform.eulerAngles.y;
            float newYaw = Mathf.MoveTowardsAngle(
                currentYaw,
                targetYaw,
                turnYawSpeed * Mathf.Max(0f, deltaTime));
            transform.rotation = Quaternion.Euler(0f, newYaw, 0f);
            YawDifference = Mathf.Abs(Mathf.DeltaAngle(newYaw, targetYaw));

            if (canConfirm && YawDifference <= facingThreshold)
            {
                ConfirmThreat();
            }
        }

        private bool EvaluateStimulus(AimThreatStimulus stimulus)
        {
            LastDistance = 0f;
            LastAngle = 180f;
            HasLineOfSight = false;
            AimThreatensTarget = false;

            if (!stimulus.IsAiming || eye == null || targetBounds == null)
            {
                return false;
            }

            Vector3 toSource = stimulus.Origin - eye.position;
            LastDistance = toSource.magnitude;
            float effectiveMaxDistance = GetEffectiveMaxDistance(stimulus);
            if (effectiveMaxDistance <= 0f || LastDistance > effectiveMaxDistance)
            {
                return false;
            }

            if (toSource.sqrMagnitude <= Mathf.Epsilon)
            {
                LastAngle = 0f;
            }
            else
            {
                LastAngle = Vector3.Angle(transform.forward, toSource.normalized);
            }

            if (LastAngle > peripheralFOV * 0.5f)
            {
                return false;
            }

            AimThreatensTarget = AimIntersectsTarget(stimulus, effectiveMaxDistance);
            if (!AimThreatensTarget)
            {
                return false;
            }

            HasLineOfSight = CheckLineOfSight(stimulus.Origin);
            return HasLineOfSight;
        }

        private void UpdateConfirmedEpisode(float elapsed)
        {
            if (_currentStimulus.IsAiming)
            {
                Suspicion = Mathf.Max(Suspicion, suspicionEnterThreshold);
                SetState(PerceptionState.ThreatConfirmed);
                return;
            }

            DecaySuspicion(elapsed);
            SetState(PerceptionState.Recovering);

            if (_releaseObserved && Suspicion <= suspicionExitThreshold)
            {
                _episodeArmed = true;
                SetState(PerceptionState.Idle);
            }
        }

        private void ConfirmThreat()
        {
            _episodeArmed = false;
            _releaseObserved = false;
            Suspicion = 1f;
            ThreatEpisodeId++;
            LastConfirmationTime = Time.realtimeSinceStartup;
            SetState(PerceptionState.ThreatConfirmed);
            ThreatConfirmed?.Invoke(this);
        }

        private void DecaySuspicion(float elapsed)
        {
            Suspicion = Mathf.Clamp01(
                Suspicion - suspicionDecayRate * Mathf.Max(0f, elapsed));
        }

        private float GetEffectiveMaxDistance(AimThreatStimulus stimulus)
        {
            return Mathf.Min(maxDistance, Mathf.Max(0f, stimulus.MaxDistance));
        }

        private bool AimIntersectsTarget(AimThreatStimulus stimulus, float effectiveMaxDistance)
        {
            if (targetBounds == null ||
                effectiveMaxDistance <= 0f ||
                stimulus.Direction.sqrMagnitude <= Mathf.Epsilon)
            {
                return false;
            }

            Bounds bounds = targetBounds.bounds;
            bounds.Expand(0.1f);
            Ray aimRay = new Ray(stimulus.Origin, stimulus.Direction.normalized);
            return bounds.IntersectRay(aimRay, out float hitDistance) &&
                hitDistance <= effectiveMaxDistance;
        }

        private bool CheckLineOfSight(Vector3 sourcePosition)
        {
            Vector3 delta = sourcePosition - eye.position;
            float distance = delta.magnitude;
            if (distance <= Mathf.Epsilon)
            {
                return true;
            }

            int hitCount = Physics.RaycastNonAlloc(
                eye.position,
                delta / distance,
                _lineOfSightHits,
                distance,
                occludersMask,
                QueryTriggerInteraction.Ignore);

            Transform sourceRoot = stimulusEmitter != null ? stimulusEmitter.transform : null;
            for (int i = 0; i < hitCount; i++)
            {
                Collider hitCollider = _lineOfSightHits[i].collider;
                if (hitCollider == null ||
                    IsInHierarchy(hitCollider.transform, transform) ||
                    IsInHierarchy(hitCollider.transform, sourceRoot))
                {
                    continue;
                }

                return false;
            }

            return true;
        }

        private void SetState(PerceptionState nextState)
        {
            if (State == nextState)
            {
                ApplyStateVisualization();
                return;
            }

            State = nextState;
            ApplyStateVisualization();
            StateChanged?.Invoke(State);
        }

        private void ApplyStateVisualization()
        {
            Color stateColor = GetStateColor(State);
            ApplyRendererColor(bodyRenderer, stateColor);
            ApplyRendererColor(facingMarkerRenderer, stateColor);
        }

        private void ApplyRendererColor(Renderer targetRenderer, Color color)
        {
            if (targetRenderer == null)
            {
                return;
            }

            if (_statePropertyBlock == null)
            {
                _statePropertyBlock = new MaterialPropertyBlock();
            }

            _statePropertyBlock.Clear();
            targetRenderer.GetPropertyBlock(_statePropertyBlock);
            _statePropertyBlock.SetColor(BaseColorPropertyId, color);
            _statePropertyBlock.SetColor(ColorPropertyId, color);
            targetRenderer.SetPropertyBlock(_statePropertyBlock);
        }

        private void ResolveReferences()
        {
            if (eye == null)
            {
                eye = transform;
            }

            if (targetBounds == null)
            {
                targetBounds = GetComponent<CharacterController>();
            }

            if (stimulusEmitter == null)
            {
                stimulusEmitter = FindFirstObjectByType<AimThreatEmitter>();
            }

            if (bodyRenderer == null)
            {
                bodyRenderer = GetComponent<Renderer>();
            }

            if (facingMarkerRenderer == null)
            {
                Transform facingMarker = transform.Find("FacingMarker");
                if (facingMarker != null)
                {
                    facingMarkerRenderer = facingMarker.GetComponent<Renderer>();
                }
            }
        }

        private static bool IsInHierarchy(Transform candidate, Transform root)
        {
            return candidate != null &&
                root != null &&
                (candidate == root || candidate.IsChildOf(root));
        }

        private void OnDrawGizmosSelected()
        {
            Transform origin = eye != null ? eye : transform;
            Vector3 forward = transform.forward;

            Gizmos.color = new Color(1f, 0.75f, 0f, 0.8f);
            DrawFovBoundary(origin.position, forward, coreFOV * 0.5f);

            Gizmos.color = new Color(0.2f, 0.65f, 1f, 0.8f);
            DrawFovBoundary(origin.position, forward, peripheralFOV * 0.5f);

            Color stateColor = GetStateColor(State);
            Vector3 stateGizmoPosition = GetStateGizmoPosition(origin);
            Gizmos.color = stateColor;
            Gizmos.DrawSphere(stateGizmoPosition, StateGizmoRadius);
            Gizmos.DrawLine(origin.position, stateGizmoPosition);

            Gizmos.color = Color.white;
            Gizmos.DrawWireSphere(stateGizmoPosition, StateGizmoRadius + 0.025f);

            Gizmos.color = stateColor;
            if (_currentStimulus.SourceId != 0)
            {
                Gizmos.DrawLine(origin.position, _currentStimulus.Origin);
            }
        }

        private Vector3 GetStateGizmoPosition(Transform origin)
        {
            Collider boundsSource = targetBounds != null
                ? targetBounds
                : GetComponent<Collider>();
            if (boundsSource != null)
            {
                Bounds bounds = boundsSource.bounds;
                return new Vector3(
                    bounds.center.x,
                    bounds.max.y + StateGizmoClearance + StateGizmoRadius,
                    bounds.center.z);
            }

            return origin.position +
                Vector3.up * (StateGizmoClearance + StateGizmoRadius);
        }

        private void DrawFovBoundary(Vector3 origin, Vector3 forward, float halfAngle)
        {
            Vector3 left = Quaternion.AngleAxis(-halfAngle, Vector3.up) * forward;
            Vector3 right = Quaternion.AngleAxis(halfAngle, Vector3.up) * forward;
            Gizmos.DrawRay(origin, left * maxDistance);
            Gizmos.DrawRay(origin, right * maxDistance);
        }

        private static Color GetStateColor(PerceptionState state)
        {
            switch (state)
            {
                case PerceptionState.Suspicious:
                    return Color.yellow;
                case PerceptionState.Orienting:
                    return new Color(1f, 0.45f, 0f);
                case PerceptionState.ThreatConfirmed:
                    return Color.red;
                case PerceptionState.Recovering:
                    return Color.cyan;
                default:
                    return Color.green;
            }
        }

#if UNITY_EDITOR
        private void OnValidate()
        {
            maxDistance = Mathf.Max(0f, maxDistance);
            coreFOV = Mathf.Clamp(coreFOV, 1f, 179f);
            peripheralFOV = Mathf.Clamp(peripheralFOV, coreFOV, 179f);
            suspicionBuildTime = Mathf.Max(0.01f, suspicionBuildTime);
            suspicionDecayRate = Mathf.Max(0f, suspicionDecayRate);
            suspicionEnterThreshold = Mathf.Clamp01(suspicionEnterThreshold);
            suspicionExitThreshold = Mathf.Clamp(
                suspicionExitThreshold,
                0f,
                suspicionEnterThreshold);
            tickRateHz = Mathf.Max(1f, tickRateHz);
            turnYawSpeed = Mathf.Max(0f, turnYawSpeed);
            facingThreshold = Mathf.Clamp(facingThreshold, 0.1f, 45f);
            ResolveReferences();
        }
#endif
    }
}
