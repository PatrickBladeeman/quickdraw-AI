using System;
using QuickDraw.Core;
using UnityEngine;

namespace QuickDraw.AI.Stimuli
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(SimpleFPSController))]
    public sealed class AimThreatEmitter : MonoBehaviour
    {
        [Header("References")]
        [SerializeField] private SimpleFPSController controller;
        [SerializeField] private Camera sourceCamera;

        [Header("Stimulus")]
        [SerializeField, Min(0f)] private float maxDistance = 30f;

        private bool _wasAiming;

        public AimThreatStimulus CurrentStimulus { get; private set; }

        public event Action<AimThreatStimulus> AimStarted;
        public event Action<AimThreatStimulus> AimEnded;

        private void Awake()
        {
            ResolveReferences();
        }

        private void OnEnable()
        {
            ResolveReferences();
            _wasAiming = controller != null && controller.IsAiming;
            CurrentStimulus = BuildStimulus(Time.time, _wasAiming);
        }

        private void LateUpdate()
        {
            RefreshStimulus(Time.time);
        }

        private void OnDisable()
        {
            _wasAiming = false;
            CurrentStimulus = BuildStimulus(Time.time, false);
        }

        private void RefreshStimulus(float timestamp)
        {
            ResolveReferences();

            bool isAiming = controller != null && controller.IsAiming;
            CurrentStimulus = BuildStimulus(timestamp, isAiming);

            if (isAiming == _wasAiming)
            {
                return;
            }

            _wasAiming = isAiming;
            if (isAiming)
            {
                AimStarted?.Invoke(CurrentStimulus);
            }
            else
            {
                AimEnded?.Invoke(CurrentStimulus);
            }
        }

        private AimThreatStimulus BuildStimulus(float timestamp, bool isAiming)
        {
            Transform sourceTransform = sourceCamera != null ? sourceCamera.transform : transform;
            return new AimThreatStimulus(
                gameObject.GetInstanceID(),
                sourceTransform.position,
                sourceTransform.forward.normalized,
                timestamp,
                maxDistance,
                isAiming);
        }

        private void ResolveReferences()
        {
            if (controller == null)
            {
                controller = GetComponent<SimpleFPSController>();
            }

            if (sourceCamera == null)
            {
                sourceCamera = GetComponentInChildren<Camera>(true);
            }
        }

#if UNITY_EDITOR
        private void OnValidate()
        {
            maxDistance = Mathf.Max(0f, maxDistance);
            ResolveReferences();
        }
#endif
    }
}

