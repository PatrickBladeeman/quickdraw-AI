using System;
using System.Collections;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

namespace QuickDraw.Tests.PlayMode
{
    public sealed class SimpleFPSControllerAcceptanceTests : InputTestFixture
    {
        private const string ControllerTypeName = "QuickDraw.Core.SimpleFPSController, Assembly-CSharp";
        private Keyboard _keyboard;
        private Mouse _mouse;

        [UnitySetUp]
        public IEnumerator SetUp()
        {
            SceneManager.LoadScene("Test_Arena", LoadSceneMode.Single);
            yield return null;
        }

        [UnityTearDown]
        public IEnumerator TearDownScene()
        {
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
            yield return null;
        }

        [Test]
        public void SceneHasRequiredConfiguredPlayerHierarchy()
        {
            Type controllerType = GetControllerType();
            GameObject player = GameObject.Find("Player");

            Assert.That(player, Is.Not.Null);
            Assert.That(player.transform.position, Is.EqualTo(new Vector3(0f, 1f, -5.5f)));

            CharacterController characterController = player.GetComponent<CharacterController>();
            Assert.That(characterController, Is.Not.Null);
            Assert.That(characterController.center, Is.EqualTo(new Vector3(0f, 1f, 0f)));
            Assert.That(characterController.height, Is.EqualTo(2f));
            Assert.That(characterController.radius, Is.EqualTo(0.4f));
            Assert.That(characterController.stepOffset, Is.EqualTo(0.3f));
            Assert.That(characterController.slopeLimit, Is.EqualTo(45f));

            Component controller = player.GetComponent(controllerType);
            Transform pivot = player.transform.Find("CameraPivot");
            Camera playerCamera = pivot != null ? pivot.GetComponentInChildren<Camera>(true) : null;

            Assert.That(controller, Is.Not.Null);
            Assert.That(pivot, Is.Not.Null);
            Assert.That(pivot.localPosition, Is.EqualTo(new Vector3(0f, 0.65f, 0f)));
            Assert.That(playerCamera, Is.Not.Null);
            Assert.That(playerCamera.transform.localPosition, Is.EqualTo(Vector3.zero));
            Assert.That(playerCamera.CompareTag("MainCamera"), Is.True);
            Assert.That(playerCamera.fieldOfView, Is.EqualTo(70f));

            Assert.That(ReadField<Transform>(controller, "cameraPivot"), Is.SameAs(pivot));
            Assert.That(ReadField<Camera>(controller, "playerCamera"), Is.SameAs(playerCamera));
        }

        [Test]
        public void ControllerExposesReadOnlyAimingStateAndRequiresCharacterController()
        {
            Type controllerType = GetControllerType();
            Assert.That(controllerType.IsSealed, Is.True);
            Assert.That(typeof(MonoBehaviour).IsAssignableFrom(controllerType), Is.True);

            PropertyInfo aimingProperty = controllerType.GetProperty("IsAiming", BindingFlags.Instance | BindingFlags.Public);
            Assert.That(aimingProperty, Is.Not.Null);
            Assert.That(aimingProperty.PropertyType, Is.EqualTo(typeof(bool)));
            Assert.That(aimingProperty.CanRead, Is.True);
            Assert.That(aimingProperty.GetSetMethod(false), Is.Null);

            RequireComponent requireComponent = controllerType.GetCustomAttribute<RequireComponent>();
            Assert.That(requireComponent, Is.Not.Null);
            Assert.That(requireComponent.m_Type0, Is.EqualTo(typeof(CharacterController)));
        }

        [UnityTest]
        public IEnumerator InputDrivesMovementLookSprintJumpAimFovAndCursorToggle()
        {
            Type controllerType = GetControllerType();
            GameObject player = GameObject.Find("Player");
            Component controller = player.GetComponent(controllerType);
            Camera playerCamera = player.GetComponentInChildren<Camera>(true);

            _keyboard = InputSystem.AddDevice<Keyboard>("Task2 Test Keyboard");
            _mouse = InputSystem.AddDevice<Mouse>("Task2 Test Mouse");
            yield return new WaitForSeconds(0.75f);

            ((Behaviour)controller).enabled = false;
            Invoke(controller, "SetCursorLocked", true);

            Vector3 normalStart = player.transform.position;
            Press(_keyboard.wKey);
            InputSystem.Update();
            Assert.That(_keyboard.wKey.isPressed, Is.True, "The simulated W press was not observed by the Input System.");
            Assert.That(ReadField<CharacterController>(controller, "_characterController"), Is.Not.Null, "Awake must cache the CharacterController.");
            TickController(controller, 12);
            Release(_keyboard.wKey);
            InputSystem.Update();
            float normalDistance = HorizontalDistance(normalStart, player.transform.position);
            Assert.That(normalDistance, Is.GreaterThan(0.05f), "W must move the player forward.");

            Vector3 sprintStart = player.transform.position;
            Press(_keyboard.wKey);
            InputSystem.Update();
            Press(_keyboard.leftShiftKey);
            InputSystem.Update();
            Assert.That(_keyboard.wKey.isPressed, Is.True);
            Assert.That(_keyboard.leftShiftKey.isPressed, Is.True);
            TickController(controller, 12);
            Release(_keyboard.wKey);
            InputSystem.Update();
            Release(_keyboard.leftShiftKey);
            InputSystem.Update();
            float sprintDistance = HorizontalDistance(sprintStart, player.transform.position);
            Assert.That(sprintDistance, Is.GreaterThan(normalDistance * 1.15f), "Shift must increase movement speed.");

            float yawBefore = player.transform.eulerAngles.y;
            float pitchBefore = player.transform.Find("CameraPivot").localEulerAngles.x;
            InputSystem.QueueDeltaStateEvent(_mouse.delta, new Vector2(40f, -20f));
            InputSystem.Update();
            TickController(controller, 1);
            Assert.That(Mathf.Abs(Mathf.DeltaAngle(yawBefore, player.transform.eulerAngles.y)), Is.GreaterThan(0.1f));
            Assert.That(Mathf.Abs(Mathf.DeltaAngle(pitchBefore, player.transform.Find("CameraPivot").localEulerAngles.x)), Is.GreaterThan(0.1f));

            float groundedY = player.transform.position.y;
            Assert.That(player.GetComponent<CharacterController>().isGrounded, Is.True, "The controller must be grounded before the jump check.");
            Press(_keyboard.spaceKey);
            InputSystem.Update();
            Assert.That(_keyboard.spaceKey.wasPressedThisFrame, Is.True, "The simulated Space press was not observed by the Input System.");
            TickController(controller, 1);
            Release(_keyboard.spaceKey);
            InputSystem.Update();
            TickController(controller, 4);
            Assert.That(player.transform.position.y, Is.GreaterThan(groundedY + 0.01f), "Space must start a jump while grounded.");

            float normalFov = playerCamera.fieldOfView;
            Press(_mouse.rightButton);
            InputSystem.Update();
            TickController(controller, 8);
            Assert.That(ReadAiming(controller), Is.True, "RMB must set IsAiming.");
            Assert.That(playerCamera.fieldOfView, Is.LessThan(normalFov), "RMB must reduce FOV smoothly.");
            Assert.That(playerCamera.fieldOfView, Is.GreaterThanOrEqualTo(55f));

            Release(_mouse.rightButton);
            InputSystem.Update();
            float aimedFov = playerCamera.fieldOfView;
            TickController(controller, 8);
            Assert.That(ReadAiming(controller), Is.False, "Releasing RMB must clear IsAiming.");
            Assert.That(playerCamera.fieldOfView, Is.GreaterThan(aimedFov), "FOV must return after releasing RMB.");

            Press(_keyboard.escapeKey);
            InputSystem.Update();
            TickController(controller, 1);
            Release(_keyboard.escapeKey);
            InputSystem.Update();
            Assert.That(ReadField<bool>(controller, "_cursorLocked"), Is.False, "Escape must release the cursor.");

            Press(_keyboard.escapeKey);
            InputSystem.Update();
            TickController(controller, 1);
            Release(_keyboard.escapeKey);
            InputSystem.Update();
            Assert.That(ReadField<bool>(controller, "_cursorLocked"), Is.True, "A second Escape press must relock the cursor.");

            yield return null;
        }

        [UnityTest]
        public IEnumerator JumpReachesConfiguredHeightAndDoesNotHangOnOverheadCollision()
        {
            Type controllerType = GetControllerType();
            GameObject player = GameObject.Find("Player");
            Component controller = player.GetComponent(controllerType);
            CharacterController characterController = player.GetComponent<CharacterController>();

            _keyboard = InputSystem.AddDevice<Keyboard>("Task2 Jump Test Keyboard");
            _mouse = InputSystem.AddDevice<Mouse>("Task2 Jump Test Mouse");
            yield return new WaitForSeconds(0.75f);

            ((Behaviour)controller).enabled = false;
            Invoke(controller, "SetCursorLocked", true);

            for (int i = 0; i < 180 && !characterController.isGrounded; i++)
            {
                TickController(controller, 1);
            }

            Assert.That(characterController.isGrounded, Is.True, "The player must settle before the jump test starts.");
            float groundedY = player.transform.position.y;
            Press(_keyboard.spaceKey);
            InputSystem.Update();
            TickController(controller, 1);
            Release(_keyboard.spaceKey);
            InputSystem.Update();

            float maximumY = player.transform.position.y;
            bool landed = false;
            for (int i = 0; i < 180; i++)
            {
                TickController(controller, 1);
                maximumY = Mathf.Max(maximumY, player.transform.position.y);
                if (i > 10 && characterController.isGrounded)
                {
                    landed = true;
                    break;
                }
            }

            Assert.That(landed, Is.True, "The unobstructed jump must return to the floor.");
            Assert.That(maximumY - groundedY, Is.InRange(0.9f, 1.2f), "The configured 1.1 m jump must not be artificially clamped.");

            GameObject overheadBlocker = GameObject.CreatePrimitive(PrimitiveType.Cube);
            overheadBlocker.name = "JumpTestOverheadBlocker";
            overheadBlocker.transform.localScale = new Vector3(2f, 0.2f, 2f);
            float blockerBottom = characterController.bounds.max.y + 0.15f;
            overheadBlocker.transform.position = new Vector3(
                player.transform.position.x,
                blockerBottom + 0.1f,
                player.transform.position.z);
            Physics.SyncTransforms();

            Press(_keyboard.spaceKey);
            InputSystem.Update();
            TickController(controller, 1);
            Release(_keyboard.spaceKey);
            InputSystem.Update();

            bool upwardVelocityCleared = false;
            for (int i = 0; i < 12; i++)
            {
                TickController(controller, 1);
                if (ReadField<float>(controller, "_verticalVelocity") <= 0f)
                {
                    upwardVelocityCleared = true;
                    break;
                }
            }

            Assert.That(upwardVelocityCleared, Is.True, "An overhead collision must clear upward velocity immediately.");
            float collisionHeight = player.transform.position.y;
            TickController(controller, 3);
            Assert.That(player.transform.position.y, Is.LessThan(collisionHeight), "The player must begin falling without an apex pause.");

            UnityEngine.Object.Destroy(overheadBlocker);
            yield return null;
        }

        private static Type GetControllerType()
        {
            Type type = Type.GetType(ControllerTypeName);
            Assert.That(type, Is.Not.Null, $"Could not find {ControllerTypeName}.");
            return type;
        }

        private static T ReadField<T>(object instance, string fieldName)
        {
            FieldInfo field = instance.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
            Assert.That(field, Is.Not.Null, $"Missing field {fieldName}.");
            return (T)field.GetValue(instance);
        }

        private static bool ReadAiming(object controller)
        {
            PropertyInfo property = controller.GetType().GetProperty("IsAiming", BindingFlags.Instance | BindingFlags.Public);
            return (bool)property.GetValue(controller);
        }

        private static void Invoke(object instance, string methodName, params object[] arguments)
        {
            MethodInfo method = instance.GetType().GetMethod(methodName, BindingFlags.Instance | BindingFlags.NonPublic);
            Assert.That(method, Is.Not.Null, $"Missing method {methodName}.");
            method.Invoke(instance, arguments);
        }

        private void TickController(object controller, int count)
        {
            for (int i = 0; i < count; i++)
            {
                Invoke(controller, "Tick", _keyboard, _mouse, 1f / 60f);
            }
        }

        private static float HorizontalDistance(Vector3 from, Vector3 to)
        {
            from.y = 0f;
            to.y = 0f;
            return Vector3.Distance(from, to);
        }
    }
}
