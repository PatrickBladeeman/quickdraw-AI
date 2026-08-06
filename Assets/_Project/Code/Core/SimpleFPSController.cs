using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.Controls;

namespace QuickDraw.Core
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(CharacterController))]
    public sealed class SimpleFPSController : MonoBehaviour
    {
        private const float MouseDegreesPerPixel = 0.1f;
        private const float GroundedVelocity = -2f;

        [Header("References")]
        [SerializeField] private Transform cameraPivot;
        [SerializeField] private Camera playerCamera;

        [Header("Movement")]
        [SerializeField, Min(0f)] private float moveSpeed = 5f;
        [SerializeField, Min(1f)] private float sprintMultiplier = 1.4f;
        [SerializeField] private float gravity = -9.81f;
        [SerializeField, Min(0f)] private float jumpHeight = 1.1f;

        [Header("Look")]
        [SerializeField, Min(0f)] private float mouseSensitivity = 1.8f;
        [SerializeField, Min(0f)] private float mouseSensitivityAim = 1.2f;
        [SerializeField, Range(1f, 89f)] private float maxPitch = 89f;

        [Header("Aim")]
        [SerializeField, Range(1f, 179f)] private float normalFOV = 70f;
        [SerializeField, Range(1f, 179f)] private float aimFOV = 55f;
        [SerializeField, Min(0f)] private float fovLerp = 12f;

        private CharacterController _characterController;
        private float _pitch;
        private float _verticalVelocity;
        private bool _cursorLocked;

        public bool IsAiming { get; private set; }

        private void Awake()
        {
            _characterController = GetComponent<CharacterController>();
            ResolveReferences();
            _pitch = NormalizePitch(cameraPivot != null ? cameraPivot.localEulerAngles.x : 0f);
        }

        private void OnEnable()
        {
            ResolveReferences();

            if (playerCamera != null)
            {
                playerCamera.fieldOfView = normalFOV;
            }

            SetCursorLocked(true);
        }

        private void OnDisable()
        {
            IsAiming = false;
            SetCursorLocked(false);
        }

        private void Update()
        {
            Tick(Keyboard.current, Mouse.current, Time.deltaTime);
        }

        private void Tick(Keyboard keyboard, Mouse mouse, float deltaTime)
        {
            if (keyboard != null && keyboard.escapeKey.wasPressedThisFrame)
            {
                SetCursorLocked(!_cursorLocked);
            }

            IsAiming = _cursorLocked && mouse != null && mouse.rightButton.isPressed;

            if (_cursorLocked && mouse != null)
            {
                ApplyLook(mouse.delta.ReadValue());
            }

            ApplyMovement(keyboard, deltaTime);
            UpdateCameraFov(deltaTime);
        }

        private void ResolveReferences()
        {
            if (cameraPivot == null)
            {
                Transform namedPivot = transform.Find("CameraPivot");
                cameraPivot = namedPivot != null ? namedPivot : transform;
            }

            if (playerCamera == null && cameraPivot != null)
            {
                playerCamera = cameraPivot.GetComponentInChildren<Camera>(true);
            }
        }

        private void ApplyMovement(Keyboard keyboard, float deltaTime)
        {
            if (_characterController == null)
            {
                return;
            }

            Vector2 moveInput = Vector2.zero;
            bool sprinting = false;
            bool jumpPressed = false;

            if (keyboard != null)
            {
                moveInput.x = ReadAxis(keyboard.aKey, keyboard.dKey);
                moveInput.y = ReadAxis(keyboard.sKey, keyboard.wKey);
                moveInput = Vector2.ClampMagnitude(moveInput, 1f);
                sprinting = keyboard.leftShiftKey.isPressed || keyboard.rightShiftKey.isPressed;
                jumpPressed = keyboard.spaceKey.wasPressedThisFrame;
            }

            if (_characterController.isGrounded && _verticalVelocity < 0f)
            {
                _verticalVelocity = GroundedVelocity;
            }

            if (jumpPressed && _characterController.isGrounded && jumpHeight > 0f && gravity < 0f)
            {
                _verticalVelocity = Mathf.Sqrt(jumpHeight * -2f * gravity);
            }

            float speed = moveSpeed * (sprinting ? sprintMultiplier : 1f);
            Vector3 horizontalVelocity =
                (transform.right * moveInput.x + transform.forward * moveInput.y) * speed;

            _verticalVelocity += gravity * deltaTime;
            Vector3 velocity = horizontalVelocity + Vector3.up * _verticalVelocity;
            _characterController.Move(velocity * deltaTime);
        }

        private void ApplyLook(Vector2 mouseDelta)
        {
            if (cameraPivot == null)
            {
                return;
            }

            float sensitivity = IsAiming ? mouseSensitivityAim : mouseSensitivity;
            Vector2 lookDelta = mouseDelta * (sensitivity * MouseDegreesPerPixel);

            _pitch = Mathf.Clamp(_pitch - lookDelta.y, -maxPitch, maxPitch);
            cameraPivot.localRotation = Quaternion.Euler(_pitch, 0f, 0f);
            transform.Rotate(Vector3.up, lookDelta.x, Space.Self);
        }

        private void UpdateCameraFov(float deltaTime)
        {
            if (playerCamera == null)
            {
                return;
            }

            float targetFov = IsAiming ? aimFOV : normalFOV;
            float blend = fovLerp <= 0f ? 1f : 1f - Mathf.Exp(-fovLerp * deltaTime);
            playerCamera.fieldOfView = Mathf.Lerp(playerCamera.fieldOfView, targetFov, blend);
        }

        private void SetCursorLocked(bool locked)
        {
            _cursorLocked = locked;
            Cursor.lockState = locked ? CursorLockMode.Locked : CursorLockMode.None;
            Cursor.visible = !locked;

            if (!locked)
            {
                IsAiming = false;
            }
        }

        private static float ReadAxis(KeyControl negative, KeyControl positive)
        {
            return (positive.isPressed ? 1f : 0f) - (negative.isPressed ? 1f : 0f);
        }

        private static float NormalizePitch(float eulerPitch)
        {
            return eulerPitch > 180f ? eulerPitch - 360f : eulerPitch;
        }

#if UNITY_EDITOR
        private void OnValidate()
        {
            moveSpeed = Mathf.Max(0f, moveSpeed);
            sprintMultiplier = Mathf.Max(1f, sprintMultiplier);
            jumpHeight = Mathf.Max(0f, jumpHeight);
            mouseSensitivity = Mathf.Max(0f, mouseSensitivity);
            mouseSensitivityAim = Mathf.Max(0f, mouseSensitivityAim);
            fovLerp = Mathf.Max(0f, fovLerp);
            aimFOV = Mathf.Min(aimFOV, normalFOV);
        }
#endif
    }
}
