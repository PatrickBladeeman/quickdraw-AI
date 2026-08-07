using System;
using System.Collections;
using System.Linq;
using System.Linq.Expressions;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

namespace QuickDraw.Tests.PlayMode
{
    public sealed class SoftFOVPerceptionAcceptanceTests
    {
        private const string ControllerTypeName = "QuickDraw.Core.SimpleFPSController, Assembly-CSharp";
        private const string EmitterTypeName = "QuickDraw.AI.Stimuli.AimThreatEmitter, Assembly-CSharp";
        private const string PerceptionTypeName = "QuickDraw.AI.Perception.SoftFOVPerception, Assembly-CSharp";
        private const string PerceptionStateTypeName = "QuickDraw.AI.Perception.PerceptionState, Assembly-CSharp";
        private const string PatrolTypeName = "QuickDraw.AI.Activity.PatrolActivity, Assembly-CSharp";
        private const string ReflexTypeName = "QuickDraw.AI.Reflex.ReflexSelector, Assembly-CSharp";

        private Type _controllerType;
        private Type _emitterType;
        private Type _perceptionType;
        private Type _patrolType;
        private GameObject _player;
        private GameObject _npc;
        private Camera _sourceCamera;
        private Component _controller;
        private Component _emitter;
        private Component _perception;
        private Component _patrol;
        private int _confirmationCount;
        private object _lastConfirmedPerception;

        [UnitySetUp]
        public IEnumerator SetUpScene()
        {
            SceneManager.LoadScene("Test_Arena", LoadSceneMode.Single);
            yield return null;

            _controllerType = RequireType(ControllerTypeName);
            _emitterType = RequireType(EmitterTypeName);
            _perceptionType = RequireType(PerceptionTypeName);
            _patrolType = RequireType(PatrolTypeName);
            _player = RequireObject("Player");
            _npc = RequireObject("NPC_01");
            _sourceCamera = _player.GetComponentInChildren<Camera>(true);
            _controller = _player.GetComponent(_controllerType);
            _emitter = _player.GetComponent(_emitterType);
            _perception = _npc.GetComponent(_perceptionType);
            _patrol = _npc.GetComponent(_patrolType);

            Assert.That(_sourceCamera, Is.Not.Null);
            Assert.That(_controller, Is.Not.Null);
            Assert.That(_emitter, Is.Not.Null);
            Assert.That(_perception, Is.Not.Null);
            Assert.That(_patrol, Is.Not.Null);

            ((Behaviour)_controller).enabled = false;
            ((Behaviour)_emitter).enabled = false;
            ((Behaviour)_perception).enabled = false;
            ((Behaviour)_patrol).enabled = false;
            Invoke(_perception, "ResetPerception");
            _confirmationCount = 0;
            _lastConfirmedPerception = null;
        }

        [UnityTearDown]
        public IEnumerator TearDownScene()
        {
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
            yield return null;
        }

        [Test]
        public void SceneContainsConfiguredIsolatedPerceptionContract()
        {
            Type stateType = RequireType(PerceptionStateTypeName);
            Type reflexType = RequireType(ReflexTypeName);
            Transform eye = _npc.transform.Find("PerceptionEye");
            Transform facingMarker = _npc.transform.Find("FacingMarker");
            CharacterController npcBounds = _npc.GetComponent<CharacterController>();

            Assert.That(_perceptionType.IsSealed, Is.True);
            Assert.That(typeof(MonoBehaviour).IsAssignableFrom(_perceptionType), Is.True);
            Assert.That(UnityEngine.Object.FindObjectsByType(_perceptionType, FindObjectsInactive.Include, FindObjectsSortMode.None), Has.Length.EqualTo(1));
            Assert.That(eye, Is.Not.Null);
            Assert.That(eye.localPosition, Is.EqualTo(new Vector3(0f, 0.65f, 0f)));
            Assert.That(facingMarker, Is.Not.Null);
            Assert.That(facingMarker.localPosition, Is.EqualTo(new Vector3(0f, 0.35f, 0.52f)));
            Assert.That(facingMarker.GetComponent<MeshRenderer>(), Is.Not.Null);
            Assert.That(facingMarker.GetComponent<Collider>(), Is.Null);
            Assert.That(Quaternion.Angle(_npc.transform.rotation, Quaternion.Euler(0f, 180f, 0f)), Is.LessThan(0.01f));

            Assert.That(ReadPrivateField<Transform>(_perception, "eye"), Is.SameAs(eye));
            Assert.That(ReadPrivateField<Component>(_perception, "stimulusEmitter"), Is.SameAs(_emitter));
            Assert.That(ReadPrivateField<Collider>(_perception, "targetBounds"), Is.SameAs(npcBounds));
            Assert.That(ReadPrivateField<LayerMask>(_perception, "occludersMask").value, Is.EqualTo(1));
            Assert.That(ReadPrivateField<Renderer>(_perception, "bodyRenderer"), Is.SameAs(_npc.GetComponent<MeshRenderer>()));
            Assert.That(ReadPrivateField<Renderer>(_perception, "facingMarkerRenderer"), Is.SameAs(facingMarker.GetComponent<MeshRenderer>()));
            Assert.That(ReadPrivateField<float>(_perception, "maxDistance"), Is.EqualTo(20f));
            Assert.That(ReadPrivateField<float>(_perception, "coreFOV"), Is.EqualTo(90f));
            Assert.That(ReadPrivateField<float>(_perception, "peripheralFOV"), Is.EqualTo(140f));
            Assert.That(ReadPrivateField<float>(_perception, "suspicionBuildTime"), Is.EqualTo(0.45f));
            Assert.That(ReadPrivateField<float>(_perception, "suspicionDecayRate"), Is.EqualTo(0.8f));
            Assert.That(ReadPrivateField<float>(_perception, "suspicionEnterThreshold"), Is.EqualTo(0.5f));
            Assert.That(ReadPrivateField<float>(_perception, "suspicionExitThreshold"), Is.EqualTo(0.3f));
            Assert.That(ReadPrivateField<float>(_perception, "tickRateHz"), Is.EqualTo(12f));
            Assert.That(ReadPrivateField<float>(_perception, "turnYawSpeed"), Is.EqualTo(300f));
            Assert.That(ReadPrivateField<float>(_perception, "facingThreshold"), Is.EqualTo(3f));

            AssertReadOnlyProperty("State", stateType);
            AssertReadOnlyProperty("Suspicion", typeof(float));
            AssertReadOnlyProperty("ThreatEpisodeId", typeof(int));
            Assert.That(_perceptionType.GetEvent("StateChanged"), Is.Not.Null);
            Assert.That(_perceptionType.GetEvent("ThreatConfirmed"), Is.Not.Null);
            Assert.That(_perceptionType.GetMethod("OnDirectThreatDetected"), Is.Null);
            Assert.That(_npc.GetComponent(reflexType), Is.Null, "Task 6 must not wire reflex execution.");

            string[] dependencies = _perceptionType
                .GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
                .Select(field => $"{field.Name} {field.FieldType.FullName}")
                .ToArray();
            Assert.That(dependencies, Has.None.Contains("Reflex"));
        }

        [Test]
        public void StateGizmoPositionClearsNpcBounds()
        {
            CharacterController npcBounds = _npc.GetComponent<CharacterController>();
            Transform eye = _npc.transform.Find("PerceptionEye");
            Physics.SyncTransforms();

            Vector3 stateGizmoPosition = InvokeWithResult<Vector3>(
                _perception,
                "GetStateGizmoPosition",
                eye);

            Assert.That(
                stateGizmoPosition.y,
                Is.GreaterThan(npcBounds.bounds.max.y + 0.2f),
                "The state indicator must sit clearly above the capsule instead of being hidden inside it.");
            Assert.That(stateGizmoPosition.x, Is.EqualTo(npcBounds.bounds.center.x).Within(0.001f));
            Assert.That(stateGizmoPosition.z, Is.EqualTo(npcBounds.bounds.center.z).Within(0.001f));
        }

        [Test]
        public void RuntimeRenderersExposePerceptionStateColors()
        {
            Renderer body = _npc.GetComponent<MeshRenderer>();
            Renderer facingMarker = _npc.transform.Find("FacingMarker").GetComponent<MeshRenderer>();
            float radius = 5f;
            float radians = 60f * Mathf.Deg2Rad;
            Vector3 peripheralSource = new Vector3(
                -Mathf.Sin(radians) * radius,
                1f,
                Mathf.Cos(radians) * radius);

            ConfigureScenario(peripheralSource, Quaternion.identity, true, 5f);
            AssertRendererColor(body, Color.green);
            AssertRendererColor(facingMarker, Color.green);

            TickPerception(0.15f);
            Assert.That(ReadState(), Is.EqualTo("Suspicious"));
            AssertRendererColor(body, Color.yellow);
            AssertRendererColor(facingMarker, Color.yellow);

            TickPerception(0.3f);
            Assert.That(ReadState(), Is.EqualTo("Orienting"));
            AssertRendererColor(body, new Color(1f, 0.45f, 0f));
            AssertRendererColor(facingMarker, new Color(1f, 0.45f, 0f));

            for (int i = 0; i < 20 && ReadState() != "ThreatConfirmed"; i++)
            {
                TickOrientation(1f / 60f);
            }

            Assert.That(ReadState(), Is.EqualTo("ThreatConfirmed"));
            AssertRendererColor(body, Color.red);
            AssertRendererColor(facingMarker, Color.red);

            SetAiming(false, 6f);
            TickPerception(0.1f);
            Assert.That(ReadState(), Is.EqualTo("Recovering"));
            AssertRendererColor(body, Color.cyan);
            AssertRendererColor(facingMarker, Color.cyan);

            TickPerception(1f);
            Assert.That(ReadState(), Is.EqualTo("Idle"));
            AssertRendererColor(body, Color.green);
            AssertRendererColor(facingMarker, Color.green);
        }

        [Test]
        public void FrontalVisibleAimConfirmsQuicklyAndOnlyOnceWhileHeld()
        {
            ConfigureScenario(
                new Vector3(0f, 1f, -5f),
                Quaternion.Euler(0f, 180f, 0f),
                true,
                10f);
            EventSubscription subscription = SubscribeToConfirmation();

            try
            {
                TickPerception(1f / 12f);
                Assert.That(ReadState(), Is.EqualTo("Orienting"));
                Assert.That(ReadProperty<float>(_perception, "Suspicion"), Is.EqualTo(1f));
                Assert.That(ReadProperty<float>(_perception, "LastAngle"), Is.LessThan(45f));
                Assert.That(ReadProperty<bool>(_perception, "HasLineOfSight"), Is.True);
                Assert.That(ReadProperty<bool>(_perception, "AimThreatensTarget"), Is.True);

                TickOrientation(0f);
                Assert.That(ReadState(), Is.EqualTo("ThreatConfirmed"));
                Assert.That(_confirmationCount, Is.EqualTo(1));
                Assert.That(_lastConfirmedPerception, Is.SameAs(_perception));
                Assert.That(ReadProperty<int>(_perception, "ThreatEpisodeId"), Is.EqualTo(1));

                for (int i = 0; i < 10; i++)
                {
                    TickPerception(1f / 12f);
                    TickOrientation(1f / 60f);
                }

                Assert.That(_confirmationCount, Is.EqualTo(1), "Holding aim must not repeat confirmation.");
                Assert.That(ReadProperty<bool>(_patrol, "IsRunning"), Is.True, "Task 6 must not interrupt patrol.");
            }
            finally
            {
                subscription.Dispose();
            }
        }

        [Test]
        public void PeripheralAimUsesMeasuredTickDeltaThenTurnsAtConfiguredSpeed()
        {
            float radius = 5f;
            float radians = 60f * Mathf.Deg2Rad;
            Vector3 sourcePosition = new Vector3(
                -Mathf.Sin(radians) * radius,
                1f,
                Mathf.Cos(radians) * radius);
            ConfigureScenario(sourcePosition, Quaternion.identity, true, 20f);
            EventSubscription subscription = SubscribeToConfirmation();

            try
            {
                TickPerception(0.15f);
                Assert.That(ReadState(), Is.EqualTo("Suspicious"));
                Assert.That(ReadProperty<float>(_perception, "Suspicion"), Is.EqualTo(1f / 6f).Within(0.001f));

                TickPerception(0.15f);
                Assert.That(ReadState(), Is.EqualTo("Suspicious"));
                Assert.That(ReadProperty<float>(_perception, "Suspicion"), Is.EqualTo(1f / 3f).Within(0.001f));

                TickPerception(0.15f);
                Assert.That(ReadState(), Is.EqualTo("Orienting"));
                Assert.That(ReadProperty<float>(_perception, "Suspicion"), Is.EqualTo(0.5f).Within(0.001f));
                Assert.That(ReadProperty<float>(_perception, "LastAngle"), Is.GreaterThan(45f).And.LessThan(70f));
                Assert.That(_confirmationCount, Is.Zero);

                float yawBefore = _npc.transform.eulerAngles.y;
                TickOrientation(1f / 60f);
                float firstTurn = Mathf.Abs(Mathf.DeltaAngle(yawBefore, _npc.transform.eulerAngles.y));
                Assert.That(firstTurn, Is.EqualTo(5f).Within(0.01f), "300 degrees/second must turn five degrees per 60 Hz frame.");

                for (int i = 0; i < 20 && _confirmationCount == 0; i++)
                {
                    TickOrientation(1f / 60f);
                }

                Assert.That(_confirmationCount, Is.EqualTo(1));
                Assert.That(ReadProperty<float>(_perception, "YawDifference"), Is.LessThanOrEqualTo(3f));
            }
            finally
            {
                subscription.Dispose();
            }
        }

        [Test]
        public void DistanceAndTotalFovHalfAnglesRejectInvalidStimuliBeforeLineOfSight()
        {
            ConfigureScenario(new Vector3(0f, 1f, 25f), Quaternion.identity, true, 30f);
            TickPerception(1f);

            Assert.That(ReadState(), Is.EqualTo("Idle"));
            Assert.That(ReadProperty<float>(_perception, "LastDistance"), Is.GreaterThan(20f));
            Assert.That(ReadProperty<bool>(_perception, "HasLineOfSight"), Is.False);

            float radius = 5f;
            float radians = 75f * Mathf.Deg2Rad;
            ConfigureScenario(
                new Vector3(Mathf.Sin(radians) * radius, 1f, Mathf.Cos(radians) * radius),
                Quaternion.identity,
                true,
                31f);
            TickPerception(1f);

            Assert.That(ReadState(), Is.EqualTo("Idle"));
            Assert.That(ReadProperty<float>(_perception, "LastAngle"), Is.GreaterThan(70f));
            Assert.That(ReadProperty<bool>(_perception, "HasLineOfSight"), Is.False);
        }

        [Test]
        public void OcclusionDividerPreventsVisualConfirmation()
        {
            GameObject divider = RequireObject("OcclusionDivider");
            divider.transform.position = new Vector3(0f, 1.4f, 0f);
            ConfigureScenario(
                new Vector3(0f, 1f, -5.5f),
                Quaternion.Euler(0f, 180f, 0f),
                true,
                40f,
                new Vector3(0f, 1f, 4.5f));
            EventSubscription subscription = SubscribeToConfirmation();

            try
            {
                Physics.SyncTransforms();
                TickPerception(1f);
                TickOrientation(1f);

                Assert.That(ReadProperty<bool>(_perception, "AimThreatensTarget"), Is.True);
                Assert.That(ReadProperty<bool>(_perception, "HasLineOfSight"), Is.False);
                Assert.That(ReadState(), Is.EqualTo("Idle"));
                Assert.That(ReadProperty<float>(_perception, "Suspicion"), Is.Zero);
                Assert.That(_confirmationCount, Is.Zero);
            }
            finally
            {
                subscription.Dispose();
            }
        }

        [Test]
        public void ReleaseRecoversBeforeASecondAimEpisodeCanConfirm()
        {
            ConfigureScenario(
                new Vector3(0f, 1f, -5f),
                Quaternion.Euler(0f, 180f, 0f),
                true,
                50f);
            EventSubscription subscription = SubscribeToConfirmation();

            try
            {
                TickPerception(1f / 12f);
                TickOrientation(0f);
                Assert.That(_confirmationCount, Is.EqualTo(1));

                SetAiming(false, 51f);
                TickPerception(0.5f);
                Assert.That(ReadState(), Is.EqualTo("Recovering"));
                Assert.That(ReadProperty<float>(_perception, "Suspicion"), Is.EqualTo(0.6f).Within(0.001f));

                SetAiming(true, 52f);
                TickPerception(0.5f);
                TickOrientation(0f);
                Assert.That(_confirmationCount, Is.EqualTo(1), "Re-aiming before recovery must not rearm confirmation.");

                SetAiming(false, 53f);
                TickPerception(0.5f);
                Assert.That(ReadState(), Is.EqualTo("Idle"));

                SetAiming(true, 54f);
                TickPerception(1f / 12f);
                TickOrientation(0f);
                Assert.That(_confirmationCount, Is.EqualTo(2));
                Assert.That(ReadProperty<int>(_perception, "ThreatEpisodeId"), Is.EqualTo(2));
            }
            finally
            {
                subscription.Dispose();
            }
        }

        [Test]
        public void QuickReleaseAndReaimTracksWithoutRepeatingConfirmation()
        {
            ConfigureScenario(
                new Vector3(0f, 1f, -5f),
                Quaternion.Euler(0f, 180f, 0f),
                true,
                70f);
            EventSubscription subscription = SubscribeToConfirmation();

            try
            {
                TickPerception(1f / 12f);
                TickOrientation(0f);
                Assert.That(ReadState(), Is.EqualTo("ThreatConfirmed"));
                Assert.That(_confirmationCount, Is.EqualTo(1));
                Assert.That(ReadProperty<int>(_perception, "ThreatEpisodeId"), Is.EqualTo(1));

                SetAiming(false, 71f);
                MovePlayerAndAimAtNpc(new Vector3(-4.33f, 1f, -2.5f), 72f);
                TickPerception(1f / 12f);

                Assert.That(
                    ReadState(),
                    Is.EqualTo("ThreatConfirmed"),
                    "A release/re-aim between perception ticks remains the same confirmed episode.");
                Assert.That(ReadProperty<bool>(_perception, "AimThreatensTarget"), Is.True);
                Assert.That(ReadProperty<bool>(_perception, "HasLineOfSight"), Is.True);
                Assert.That(
                    ReadProperty<float>(_perception, "LastAngle"),
                    Is.GreaterThan(45f).And.LessThan(70f));

                float yawBeforeTracking = _npc.transform.eulerAngles.y;
                TickOrientation(1f / 60f);
                float trackedTurn = Mathf.Abs(Mathf.DeltaAngle(
                    yawBeforeTracking,
                    _npc.transform.eulerAngles.y));

                Assert.That(
                    trackedTurn,
                    Is.EqualTo(5f).Within(0.01f),
                    "A confirmed episode must continue tracking a renewed valid aim at 300 degrees/second.");
                Assert.That(_confirmationCount, Is.EqualTo(1));
                Assert.That(ReadProperty<int>(_perception, "ThreatEpisodeId"), Is.EqualTo(1));

                _sourceCamera.transform.rotation = Quaternion.LookRotation(Vector3.up, Vector3.forward);
                Invoke(_emitter, "RefreshStimulus", 73f);
                TickPerception(1f / 12f);
                float yawBeforeInvalidAim = _npc.transform.eulerAngles.y;
                TickOrientation(0.25f);

                Assert.That(
                    Mathf.Abs(Mathf.DeltaAngle(yawBeforeInvalidAim, _npc.transform.eulerAngles.y)),
                    Is.LessThan(0.001f),
                    "Confirmed tracking must stop when the aim no longer intersects the NPC.");
                Assert.That(_confirmationCount, Is.EqualTo(1));
                Assert.That(ReadProperty<int>(_perception, "ThreatEpisodeId"), Is.EqualTo(1));
            }
            finally
            {
                subscription.Dispose();
            }
        }

        [UnityTest]
        public IEnumerator RealFrameSchedulerConfirmsAndRecoversWithoutManualTicks()
        {
            ConfigureScenario(
                new Vector3(0f, 1f, -5f),
                Quaternion.Euler(0f, 180f, 0f),
                true,
                60f);
            EventSubscription subscription = SubscribeToConfirmation();
            ((Behaviour)_emitter).enabled = true;
            ((Behaviour)_perception).enabled = true;

            try
            {
                for (int i = 0; i < 60 && _confirmationCount == 0; i++)
                {
                    yield return null;
                }

                Assert.That(_confirmationCount, Is.EqualTo(1));
                Assert.That(ReadState(), Is.EqualTo("ThreatConfirmed"));

                for (int i = 0; i < 10; i++)
                {
                    yield return null;
                }

                Assert.That(_confirmationCount, Is.EqualTo(1));
                SetAiming(false, 61f);

                yield return new WaitForSeconds(1.25f);

                Assert.That(ReadState(), Is.EqualTo("Idle"));
                Assert.That(_confirmationCount, Is.EqualTo(1));
            }
            finally
            {
                ((Behaviour)_perception).enabled = false;
                ((Behaviour)_emitter).enabled = false;
                subscription.Dispose();
            }
        }

        private void ConfigureScenario(
            Vector3 playerPosition,
            Quaternion npcRotation,
            bool isAiming,
            float timestamp,
            Vector3? npcPosition = null)
        {
            _npc.transform.SetPositionAndRotation(npcPosition ?? new Vector3(0f, 1f, 0f), npcRotation);
            _player.transform.SetPositionAndRotation(playerPosition, Quaternion.identity);
            Transform pivot = _player.transform.Find("CameraPivot");
            if (pivot != null)
            {
                pivot.localRotation = Quaternion.identity;
            }

            Physics.SyncTransforms();
            Vector3 target = _npc.GetComponent<CharacterController>().bounds.center;
            _sourceCamera.transform.rotation = Quaternion.LookRotation(
                (target - _sourceCamera.transform.position).normalized,
                Vector3.up);
            Physics.SyncTransforms();

            Invoke(_perception, "ResetPerception");
            SetAiming(isAiming, timestamp);
        }

        private void SetAiming(bool isAiming, float timestamp)
        {
            PropertyInfo property = _controllerType.GetProperty("IsAiming", BindingFlags.Instance | BindingFlags.Public);
            MethodInfo setter = property?.GetSetMethod(true);
            Assert.That(setter, Is.Not.Null);
            setter.Invoke(_controller, new object[] { isAiming });
            Invoke(_emitter, "RefreshStimulus", timestamp);
        }

        private void MovePlayerAndAimAtNpc(Vector3 playerPosition, float timestamp)
        {
            _player.transform.position = playerPosition;
            Transform pivot = _player.transform.Find("CameraPivot");
            if (pivot != null)
            {
                pivot.localRotation = Quaternion.identity;
            }

            Physics.SyncTransforms();
            Vector3 target = _npc.GetComponent<CharacterController>().bounds.center;
            _sourceCamera.transform.rotation = Quaternion.LookRotation(
                (target - _sourceCamera.transform.position).normalized,
                Vector3.up);
            Physics.SyncTransforms();
            SetAiming(true, timestamp);
        }

        private void TickPerception(float elapsed)
        {
            Invoke(_perception, "TickPerception", elapsed);
        }

        private void TickOrientation(float deltaTime)
        {
            Invoke(_perception, "TickOrientation", deltaTime);
        }

        private string ReadState()
        {
            return ReadProperty<object>(_perception, "State").ToString();
        }

        private EventSubscription SubscribeToConfirmation()
        {
            EventInfo eventInfo = _perceptionType.GetEvent("ThreatConfirmed");
            Assert.That(eventInfo, Is.Not.Null);
            Type sourceType = eventInfo.EventHandlerType.GetGenericArguments()[0];
            ParameterExpression source = Expression.Parameter(sourceType, "source");
            MethodInfo captureMethod = GetType().GetMethod(
                nameof(CaptureConfirmation),
                BindingFlags.Instance | BindingFlags.NonPublic);
            MethodCallExpression captureCall = Expression.Call(
                Expression.Constant(this),
                captureMethod,
                Expression.Convert(source, typeof(object)));
            Delegate handler = Expression.Lambda(eventInfo.EventHandlerType, captureCall, source).Compile();
            eventInfo.AddEventHandler(_perception, handler);
            return new EventSubscription(eventInfo, _perception, handler);
        }

        private void CaptureConfirmation(object perception)
        {
            _confirmationCount++;
            _lastConfirmedPerception = perception;
        }

        private void AssertReadOnlyProperty(string propertyName, Type propertyType)
        {
            PropertyInfo property = _perceptionType.GetProperty(propertyName, BindingFlags.Instance | BindingFlags.Public);
            Assert.That(property, Is.Not.Null);
            Assert.That(property.PropertyType, Is.EqualTo(propertyType));
            Assert.That(property.CanRead, Is.True);
            Assert.That(property.GetSetMethod(false), Is.Null);
        }

        private static Type RequireType(string qualifiedName)
        {
            Type type = Type.GetType(qualifiedName);
            Assert.That(type, Is.Not.Null, $"Could not find {qualifiedName}.");
            return type;
        }

        private static GameObject RequireObject(string objectName)
        {
            GameObject result = GameObject.Find(objectName);
            Assert.That(result, Is.Not.Null, $"Missing {objectName}.");
            return result;
        }

        private static T ReadPrivateField<T>(object instance, string fieldName)
        {
            FieldInfo field = instance.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
            Assert.That(field, Is.Not.Null, $"Missing field {fieldName}.");
            return (T)field.GetValue(instance);
        }

        private static T ReadProperty<T>(object instance, string propertyName)
        {
            PropertyInfo property = instance.GetType().GetProperty(propertyName, BindingFlags.Instance | BindingFlags.Public);
            Assert.That(property, Is.Not.Null, $"Missing property {propertyName}.");
            return (T)property.GetValue(instance);
        }

        private static void AssertRendererColor(Renderer renderer, Color expected)
        {
            MaterialPropertyBlock propertyBlock = new MaterialPropertyBlock();
            renderer.GetPropertyBlock(propertyBlock);
            Color actual = propertyBlock.GetColor(Shader.PropertyToID("_BaseColor"));
            Assert.That(actual.r, Is.EqualTo(expected.r).Within(0.001f));
            Assert.That(actual.g, Is.EqualTo(expected.g).Within(0.001f));
            Assert.That(actual.b, Is.EqualTo(expected.b).Within(0.001f));
            Assert.That(actual.a, Is.EqualTo(expected.a).Within(0.001f));
        }

        private static void Invoke(object instance, string methodName, params object[] arguments)
        {
            MethodInfo method = instance.GetType().GetMethod(
                methodName,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            Assert.That(method, Is.Not.Null, $"Missing method {methodName}.");
            method.Invoke(instance, arguments);
        }

        private static T InvokeWithResult<T>(
            object instance,
            string methodName,
            params object[] arguments)
        {
            MethodInfo method = instance.GetType().GetMethod(
                methodName,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            Assert.That(method, Is.Not.Null, $"Missing method {methodName}.");
            return (T)method.Invoke(instance, arguments);
        }

        private sealed class EventSubscription : IDisposable
        {
            private readonly EventInfo _eventInfo;
            private readonly object _source;
            private readonly Delegate _handler;

            public EventSubscription(EventInfo eventInfo, object source, Delegate handler)
            {
                _eventInfo = eventInfo;
                _source = source;
                _handler = handler;
            }

            public void Dispose()
            {
                _eventInfo.RemoveEventHandler(_source, _handler);
            }
        }
    }
}
