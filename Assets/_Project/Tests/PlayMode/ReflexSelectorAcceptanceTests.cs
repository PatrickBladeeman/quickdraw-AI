using System;
using System.Collections;
using System.Linq;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

namespace QuickDraw.Tests.PlayMode
{
    public sealed class ReflexSelectorAcceptanceTests
    {
        private const string ControllerTypeName = "QuickDraw.Core.SimpleFPSController, Assembly-CSharp";
        private const string EmitterTypeName = "QuickDraw.AI.Stimuli.AimThreatEmitter, Assembly-CSharp";
        private const string PerceptionTypeName = "QuickDraw.AI.Perception.SoftFOVPerception, Assembly-CSharp";
        private const string PatrolTypeName = "QuickDraw.AI.Activity.PatrolActivity, Assembly-CSharp";
        private const string BehaviorTypeName = "QuickDraw.AI.Behavior.NpcBehaviorController, Assembly-CSharp";
        private const string ReflexTypeName = "QuickDraw.AI.Reflex.ReflexSelector, Assembly-CSharp";
        private const string ExpectedVariant = "Flinch_StepBack";
        private const string ExpectedEventName = "reflex_commanded";

        private Type _controllerType;
        private Type _perceptionType;
        private Type _patrolType;
        private Type _behaviorType;
        private Type _reflexType;
        private GameObject _player;
        private GameObject _npc;
        private Camera _sourceCamera;
        private Component _controller;
        private Component _emitter;
        private Component _perception;
        private Component _patrol;
        private Component _behavior;
        private Component _reflex;

        [UnitySetUp]
        public IEnumerator SetUpScene()
        {
            SceneManager.LoadScene("Test_Arena", LoadSceneMode.Single);
            yield return null;

            _controllerType = RequireType(ControllerTypeName);
            Type emitterType = RequireType(EmitterTypeName);
            _perceptionType = RequireType(PerceptionTypeName);
            _patrolType = RequireType(PatrolTypeName);
            _behaviorType = RequireType(BehaviorTypeName);
            _reflexType = RequireType(ReflexTypeName);
            _player = RequireObject("Player");
            _npc = RequireObject("NPC_01");
            _sourceCamera = _player.GetComponentInChildren<Camera>(true);
            _controller = _player.GetComponent(_controllerType);
            _emitter = _player.GetComponent(emitterType);
            _perception = _npc.GetComponent(_perceptionType);
            _patrol = _npc.GetComponent(_patrolType);
            _behavior = _npc.GetComponent(_behaviorType);
            _reflex = _npc.GetComponent(_reflexType);

            Assert.That(_sourceCamera, Is.Not.Null);
            Assert.That(_controller, Is.Not.Null);
            Assert.That(_emitter, Is.Not.Null);
            Assert.That(_perception, Is.Not.Null);
            Assert.That(_patrol, Is.Not.Null);
            Assert.That(_behavior, Is.Not.Null);
            Assert.That(_reflex, Is.Not.Null);

            ((Behaviour)_controller).enabled = false;
            ((Behaviour)_emitter).enabled = false;
            ((Behaviour)_perception).enabled = false;
            ((Behaviour)_patrol).enabled = false;
            Invoke(_perception, "ResetPerception");
            Invoke(_patrol, "ResetActivity");
            Invoke(_behavior, "ResetCoordination");
        }

        [UnityTearDown]
        public IEnumerator TearDownScene()
        {
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
            yield return null;
        }

        [Test]
        public void SceneContainsScopedReflexContractAndStableConfiguration()
        {
            Assert.That(_reflexType.IsSealed, Is.True);
            Assert.That(typeof(MonoBehaviour).IsAssignableFrom(_reflexType), Is.True);
            Assert.That(
                UnityEngine.Object.FindObjectsByType(
                    _reflexType,
                    FindObjectsInactive.Include,
                    FindObjectsSortMode.None),
                Has.Length.EqualTo(1));
            Assert.That(ReadPrivateField<Component>(_behavior, "reflexSelector"), Is.SameAs(_reflex));
            Assert.That(ReadPrivateField<int>(_reflex, "styleSeed"), Is.EqualTo(1001));
            Assert.That(ReadPrivateField<float>(_reflex, "stepBackDistance"), Is.EqualTo(0.35f));
            Assert.That(ReadPrivateField<float>(_reflex, "stepDistanceVariation"), Is.EqualTo(0.05f));
            Assert.That(ReadPrivateField<float>(_reflex, "maximumYawOffset"), Is.EqualTo(30f));

            AssertReadOnlyProperty("CommandCount", typeof(int));
            AssertReadOnlyProperty("LastCommandedThreatEpisodeId", typeof(int));
            AssertReadOnlyProperty("LastCommandedVariant", typeof(string));
            AssertReadOnlyProperty("LastConfirmedThreatTime", typeof(float));
            AssertReadOnlyProperty("LastCommandTime", typeof(float));
            AssertReadOnlyProperty("LastRequestedStepDistance", typeof(float));
            AssertReadOnlyProperty("LastAppliedStepDistance", typeof(float));
            AssertReadOnlyProperty("LastYawOffset", typeof(float));
            AssertReadOnlyProperty("LastCollisionFlags", typeof(CollisionFlags));

            EventInfo commandedEvent = _reflexType.GetEvent("ReflexCommanded");
            Assert.That(commandedEvent, Is.Not.Null);
            Assert.That(commandedEvent.EventHandlerType, Is.EqualTo(typeof(Action)));
            Assert.That(ReadConstant("FlinchStepBackVariant"), Is.EqualTo(ExpectedVariant));
            Assert.That(ReadConstant("ReflexCommandedEventName"), Is.EqualTo(ExpectedEventName));
            Assert.That(_reflexType.GetMethod("OnThreatEvent"), Is.Null);

            string[] dependencies = _reflexType
                .GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
                .Select(field => $"{field.Name} {field.FieldType.FullName}")
                .ToArray();
            Assert.That(dependencies, Has.None.Contains("Logging"));
            Assert.That(dependencies, Has.None.Contains("System.Random"));
            Assert.That(dependencies, Has.None.Contains("Animator"));
        }

        [Test]
        public void CompletedInterruptionCommandsOneImmediateVisibleReflex()
        {
            int eventCount = 0;
            bool patrolWasStoppedAtCommand = false;
            Action handler = () =>
            {
                eventCount++;
                patrolWasStoppedAtCommand = !ReadProperty<bool>(_patrol, "IsRunning");
            };
            EventInfo commandedEvent = _reflexType.GetEvent("ReflexCommanded");
            commandedEvent.AddEventHandler(_reflex, handler);

            try
            {
                ConfigureFrontalAim(10f);
                Vector3 positionBeforeConfirmation = _npc.transform.position;

                ConfirmCurrentThreat();

                float confirmationTime = ReadProperty<float>(_perception, "LastConfirmationTime");
                Assert.That(eventCount, Is.EqualTo(1));
                Assert.That(patrolWasStoppedAtCommand, Is.True);
                Assert.That(ReadProperty<int>(_behavior, "InterruptionCount"), Is.EqualTo(1));
                Assert.That(ReadProperty<int>(_reflex, "CommandCount"), Is.EqualTo(1));
                Assert.That(ReadProperty<int>(_reflex, "LastCommandedThreatEpisodeId"), Is.EqualTo(1));
                Assert.That(ReadProperty<string>(_reflex, "LastCommandedVariant"), Is.EqualTo(ExpectedVariant));
                Assert.That(ReadProperty<float>(_reflex, "LastConfirmedThreatTime"), Is.EqualTo(confirmationTime));
                Assert.That(ReadProperty<float>(_reflex, "LastCommandTime"), Is.GreaterThanOrEqualTo(confirmationTime));
                Assert.That(ReadProperty<float>(_reflex, "LastRequestedStepDistance"), Is.InRange(0.1f, 0.6f));
                Assert.That(ReadProperty<float>(_reflex, "LastAppliedStepDistance"), Is.GreaterThan(0.1f));
                Assert.That(HorizontalDistance(positionBeforeConfirmation, _npc.transform.position), Is.GreaterThan(0.1f));

                Vector3 positionAfterCommand = _npc.transform.position;
                Invoke(_behavior, "HandleThreatConfirmed", _perception);
                Invoke(_behavior, "HandleThreatConfirmed", _perception);
                for (int i = 0; i < 5; i++)
                {
                    Invoke(_perception, "TickPerception", 1f / 12f);
                    Invoke(_perception, "TickOrientation", 1f / 60f);
                }

                Assert.That(eventCount, Is.EqualTo(1));
                Assert.That(ReadProperty<int>(_reflex, "CommandCount"), Is.EqualTo(1));
                Assert.That(_npc.transform.position, Is.EqualTo(positionAfterCommand));
            }
            finally
            {
                commandedEvent.RemoveEventHandler(_reflex, handler);
            }
        }

        [Test]
        public void SerializedStyleSeedIsRepeatableAndIndependentOfObjectName()
        {
            Vector3 initialPosition = _npc.transform.position;
            Quaternion initialRotation = _npc.transform.rotation;

            Assert.That(
                InvokeResult<bool>(_reflex, "TryCommandFlinchStepBack", 7, 10f),
                Is.True);
            float firstDistance = ReadProperty<float>(_reflex, "LastRequestedStepDistance");
            float firstYaw = ReadProperty<float>(_reflex, "LastYawOffset");

            Invoke(_reflex, "ResetReflex");
            CharacterController characterController = _npc.GetComponent<CharacterController>();
            characterController.enabled = false;
            _npc.transform.SetPositionAndRotation(initialPosition, initialRotation);
            _npc.name = "NameDoesNotDriveReflexStyle";
            characterController.enabled = true;
            Physics.SyncTransforms();

            Assert.That(
                InvokeResult<bool>(_reflex, "TryCommandFlinchStepBack", 7, 20f),
                Is.True);
            Assert.That(ReadProperty<float>(_reflex, "LastRequestedStepDistance"), Is.EqualTo(firstDistance));
            Assert.That(ReadProperty<float>(_reflex, "LastYawOffset"), Is.EqualTo(firstYaw));
        }

        [Test]
        public void RearmedThreatWithoutResumedActivityDoesNotCommandAnotherReflex()
        {
            ConfigureFrontalAim(30f);
            ConfirmCurrentThreat();
            Assert.That(ReadProperty<int>(_behavior, "InterruptionCount"), Is.EqualTo(1));
            Assert.That(ReadProperty<int>(_reflex, "CommandCount"), Is.EqualTo(1));

            SetAiming(false, 31f);
            Invoke(_perception, "TickPerception", 1f);
            Assert.That(ReadProperty<object>(_perception, "State").ToString(), Is.EqualTo("Idle"));
            Assert.That(ReadProperty<bool>(_patrol, "IsRunning"), Is.False);

            SetAiming(true, 32f);
            ConfirmCurrentThreat(1f);

            Assert.That(ReadProperty<int>(_perception, "ThreatEpisodeId"), Is.EqualTo(2));
            Assert.That(ReadProperty<int>(_behavior, "InterruptionCount"), Is.EqualTo(1));
            Assert.That(ReadProperty<int>(_reflex, "CommandCount"), Is.EqualTo(1));
            Assert.That(ReadProperty<int>(_reflex, "LastCommandedThreatEpisodeId"), Is.EqualTo(1));
        }

        [Test]
        public void StepBackUsesCharacterControllerCollisionAtArenaWall()
        {
            WritePrivateField(_reflex, "stepBackDistance", 0.6f);
            WritePrivateField(_reflex, "stepDistanceVariation", 0f);
            WritePrivateField(_reflex, "maximumYawOffset", 0f);

            CharacterController characterController = _npc.GetComponent<CharacterController>();
            Collider northWall = RequireObject("Wall_North").GetComponent<Collider>();
            float startingZ = northWall.bounds.min.z - characterController.radius - 0.02f;
            characterController.enabled = false;
            _npc.transform.SetPositionAndRotation(
                new Vector3(0f, _npc.transform.position.y, startingZ),
                Quaternion.LookRotation(Vector3.back, Vector3.up));
            characterController.enabled = true;
            Physics.SyncTransforms();

            Assert.That(
                InvokeResult<bool>(
                    _reflex,
                    "TryCommandFlinchStepBack",
                    99,
                    Time.realtimeSinceStartup),
                Is.True);

            CollisionFlags collisionFlags = ReadProperty<CollisionFlags>(_reflex, "LastCollisionFlags");
            Assert.That(
                characterController.bounds.max.z,
                Is.LessThanOrEqualTo(northWall.bounds.min.z + 0.01f));
            Assert.That(ReadProperty<float>(_reflex, "LastRequestedStepDistance"), Is.EqualTo(0.6f));
            Assert.That(ReadProperty<float>(_reflex, "LastAppliedStepDistance"), Is.LessThan(0.2f));
            Assert.That(collisionFlags.HasFlag(CollisionFlags.Sides), Is.True);
            Assert.That(ReadProperty<int>(_reflex, "CommandCount"), Is.EqualTo(1));
        }

        private void ConfigureFrontalAim(float timestamp)
        {
            Vector3 playerPosition = _npc.transform.position + _npc.transform.forward * 5f;
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

        private void ConfirmCurrentThreat(float orientationDeltaTime = 0f)
        {
            Invoke(_perception, "TickPerception", 1f / 12f);
            Assert.That(ReadProperty<object>(_perception, "State").ToString(), Is.EqualTo("Orienting"));
            Invoke(_perception, "TickOrientation", orientationDeltaTime);
            Assert.That(ReadProperty<object>(_perception, "State").ToString(), Is.EqualTo("ThreatConfirmed"));
        }

        private void SetAiming(bool isAiming, float timestamp)
        {
            PropertyInfo property = _controllerType.GetProperty(
                "IsAiming",
                BindingFlags.Instance | BindingFlags.Public);
            MethodInfo setter = property?.GetSetMethod(true);
            Assert.That(setter, Is.Not.Null);
            setter.Invoke(_controller, new object[] { isAiming });
            Invoke(_emitter, "RefreshStimulus", timestamp);
        }

        private void AssertReadOnlyProperty(string propertyName, Type propertyType)
        {
            PropertyInfo property = _reflexType.GetProperty(
                propertyName,
                BindingFlags.Instance | BindingFlags.Public);
            Assert.That(property, Is.Not.Null);
            Assert.That(property.PropertyType, Is.EqualTo(propertyType));
            Assert.That(property.CanRead, Is.True);
            Assert.That(property.GetSetMethod(false), Is.Null);
        }

        private string ReadConstant(string fieldName)
        {
            FieldInfo field = _reflexType.GetField(
                fieldName,
                BindingFlags.Static | BindingFlags.Public);
            Assert.That(field, Is.Not.Null);
            return (string)field.GetRawConstantValue();
        }

        private static float HorizontalDistance(Vector3 a, Vector3 b)
        {
            return Vector3.ProjectOnPlane(a - b, Vector3.up).magnitude;
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
            FieldInfo field = instance.GetType().GetField(
                fieldName,
                BindingFlags.Instance | BindingFlags.NonPublic);
            Assert.That(field, Is.Not.Null, $"Missing field {fieldName}.");
            return (T)field.GetValue(instance);
        }

        private static void WritePrivateField(object instance, string fieldName, object value)
        {
            FieldInfo field = instance.GetType().GetField(
                fieldName,
                BindingFlags.Instance | BindingFlags.NonPublic);
            Assert.That(field, Is.Not.Null, $"Missing field {fieldName}.");
            field.SetValue(instance, value);
        }

        private static T ReadProperty<T>(object instance, string propertyName)
        {
            PropertyInfo property = instance.GetType().GetProperty(
                propertyName,
                BindingFlags.Instance | BindingFlags.Public);
            Assert.That(property, Is.Not.Null, $"Missing property {propertyName}.");
            return (T)property.GetValue(instance);
        }

        private static void Invoke(object instance, string methodName, params object[] arguments)
        {
            MethodInfo method = instance.GetType().GetMethod(
                methodName,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            Assert.That(method, Is.Not.Null, $"Missing method {methodName}.");
            method.Invoke(instance, arguments);
        }

        private static T InvokeResult<T>(object instance, string methodName, params object[] arguments)
        {
            MethodInfo method = instance.GetType().GetMethod(
                methodName,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            Assert.That(method, Is.Not.Null, $"Missing method {methodName}.");
            return (T)method.Invoke(instance, arguments);
        }
    }
}
