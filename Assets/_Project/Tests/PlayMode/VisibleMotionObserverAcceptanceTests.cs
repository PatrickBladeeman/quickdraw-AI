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
    public sealed class VisibleMotionObserverAcceptanceTests
    {
        private const string ControllerTypeName = "QuickDraw.Core.SimpleFPSController, Assembly-CSharp";
        private const string EmitterTypeName = "QuickDraw.AI.Stimuli.AimThreatEmitter, Assembly-CSharp";
        private const string PerceptionTypeName = "QuickDraw.AI.Perception.SoftFOVPerception, Assembly-CSharp";
        private const string PatrolTypeName = "QuickDraw.AI.Activity.PatrolActivity, Assembly-CSharp";
        private const string BehaviorTypeName = "QuickDraw.AI.Behavior.NpcBehaviorController, Assembly-CSharp";
        private const string ReflexTypeName = "QuickDraw.AI.Reflex.ReflexSelector, Assembly-CSharp";
        private const string ObserverTypeName = "QuickDraw.AI.Reflex.VisibleMotionObserver, Assembly-CSharp";

        private Type _controllerType;
        private Type _perceptionType;
        private Type _patrolType;
        private Type _behaviorType;
        private Type _reflexType;
        private Type _observerType;
        private GameObject _player;
        private GameObject _npc;
        private Camera _sourceCamera;
        private Component _controller;
        private Component _emitter;
        private Component _perception;
        private Component _patrol;
        private Component _behavior;
        private Component _reflex;
        private Component _observer;

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
            _observerType = RequireType(ObserverTypeName);
            _player = RequireObject("Player");
            _npc = RequireObject("NPC_01");
            _sourceCamera = _player.GetComponentInChildren<Camera>(true);
            _controller = _player.GetComponent(_controllerType);
            _emitter = _player.GetComponent(emitterType);
            _perception = _npc.GetComponent(_perceptionType);
            _patrol = _npc.GetComponent(_patrolType);
            _behavior = _npc.GetComponent(_behaviorType);
            _reflex = _npc.GetComponent(_reflexType);
            _observer = _npc.GetComponent(_observerType);

            Assert.That(_sourceCamera, Is.Not.Null);
            Assert.That(_controller, Is.Not.Null);
            Assert.That(_emitter, Is.Not.Null);
            Assert.That(_perception, Is.Not.Null);
            Assert.That(_patrol, Is.Not.Null);
            Assert.That(_behavior, Is.Not.Null);
            Assert.That(_reflex, Is.Not.Null);
            Assert.That(_observer, Is.Not.Null);

            ((Behaviour)_controller).enabled = false;
            ((Behaviour)_emitter).enabled = false;
            ((Behaviour)_perception).enabled = false;
            ((Behaviour)_patrol).enabled = false;
            Invoke(_perception, "ResetPerception");
            Invoke(_patrol, "ResetActivity");
            Invoke(_behavior, "ResetCoordination");
            Invoke(_observer, "ResetObservation");
        }

        [UnityTearDown]
        public IEnumerator TearDownScene()
        {
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
            yield return null;
        }

        [Test]
        public void SceneContainsIsolatedVisibleMotionObserverContract()
        {
            Assert.That(_observerType.IsSealed, Is.True);
            Assert.That(typeof(MonoBehaviour).IsAssignableFrom(_observerType), Is.True);
            Assert.That(
                UnityEngine.Object.FindObjectsByType(
                    _observerType,
                    FindObjectsInactive.Include,
                    FindObjectsSortMode.None),
                Has.Length.EqualTo(1));
            Assert.That(ReadPrivateField<Component>(_observer, "reflexSelector"), Is.SameAs(_reflex));
            Assert.That(ReadPrivateField<float>(_observer, "positionThreshold"), Is.EqualTo(0.01f));
            Assert.That(ReadPrivateField<float>(_observer, "rotationThresholdDegrees"), Is.EqualTo(1f));

            AssertReadOnlyProperty("IsAwaitingVisibleMotion", typeof(bool));
            AssertReadOnlyProperty("VisibleMotionCount", typeof(int));
            AssertReadOnlyProperty("LastObservedThreatEpisodeId", typeof(int));
            AssertReadOnlyProperty("LastSignal", typeof(string));
            AssertReadOnlyProperty("LastConfirmedThreatTime", typeof(float));
            AssertReadOnlyProperty("LastCommandTime", typeof(float));
            AssertReadOnlyProperty("LastVisibleMotionTime", typeof(float));
            AssertReadOnlyProperty("LastPositionDelta", typeof(float));
            AssertReadOnlyProperty("LastRotationDelta", typeof(float));
            AssertReadOnlyProperty("CommandToVisibleMilliseconds", typeof(float));
            AssertReadOnlyProperty("ConfirmationToVisibleMilliseconds", typeof(float));

            EventInfo visibleEvent = _observerType.GetEvent("VisibleMotionStarted");
            Assert.That(visibleEvent, Is.Not.Null);
            Assert.That(visibleEvent.EventHandlerType, Is.EqualTo(typeof(Action)));
            Assert.That(
                ReadConstant(_observerType, "VisibleMotionStartedEventName"),
                Is.EqualTo("visible_motion_started"));

            string[] dependencies = _observerType
                .GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
                .Select(field => $"{field.Name} {field.FieldType.FullName}")
                .ToArray();
            Assert.That(dependencies, Has.None.Contains("Logging"));
            Assert.That(dependencies, Has.None.Contains("File"));
        }

        [Test]
        public void ReflexCommandAndObservedVisibleMotionRemainSeparateOneShotEvents()
        {
            int commandEventCount = 0;
            int visibleEventCount = 0;
            Action commandHandler = () => commandEventCount++;
            Action visibleHandler = () => visibleEventCount++;
            EventInfo commandEvent = _reflexType.GetEvent("ReflexCommanded");
            EventInfo visibleEvent = _observerType.GetEvent("VisibleMotionStarted");
            commandEvent.AddEventHandler(_reflex, commandHandler);
            visibleEvent.AddEventHandler(_observer, visibleHandler);

            try
            {
                ConfigureFrontalAim(10f);
                ConfirmCurrentThreat();

                Assert.That(commandEventCount, Is.EqualTo(1));
                Assert.That(visibleEventCount, Is.Zero);
                Assert.That(ReadProperty<bool>(_observer, "IsAwaitingVisibleMotion"), Is.True);
                Assert.That(ReadProperty<int>(_observer, "VisibleMotionCount"), Is.Zero);

                float commandTime = ReadProperty<float>(_reflex, "LastCommandTime");
                Invoke(_observer, "TickObservation", commandTime + 0.02f);

                Assert.That(visibleEventCount, Is.EqualTo(1));
                Assert.That(ReadProperty<bool>(_observer, "IsAwaitingVisibleMotion"), Is.False);
                Assert.That(ReadProperty<int>(_observer, "VisibleMotionCount"), Is.EqualTo(1));
                Assert.That(ReadProperty<int>(_observer, "LastObservedThreatEpisodeId"), Is.EqualTo(1));
                Assert.That(ReadProperty<string>(_observer, "LastSignal"), Does.StartWith("root_"));
                Assert.That(ReadProperty<float>(_observer, "LastVisibleMotionTime"), Is.GreaterThan(commandTime));
                Assert.That(
                    ReadProperty<float>(_observer, "CommandToVisibleMilliseconds"),
                    Is.EqualTo(20f).Within(0.05f));
                Assert.That(
                    ReadProperty<float>(_observer, "ConfirmationToVisibleMilliseconds"),
                    Is.GreaterThanOrEqualTo(20f));

                Invoke(_observer, "TickObservation", commandTime + 1f);
                Assert.That(visibleEventCount, Is.EqualTo(1));
                Assert.That(ReadProperty<int>(_observer, "VisibleMotionCount"), Is.EqualTo(1));
            }
            finally
            {
                commandEvent.RemoveEventHandler(_reflex, commandHandler);
                visibleEvent.RemoveEventHandler(_observer, visibleHandler);
            }
        }

        [Test]
        public void SubThresholdRootChangesDoNotClaimVisibleOnset()
        {
            Assert.That(
                InvokeResult<bool>(_reflex, "TryCommandFlinchStepBack", 5, 10f),
                Is.True);
            Vector3 baselinePosition = ReadProperty<Vector3>(_reflex, "LastCommandStartPosition");
            Quaternion baselineRotation = ReadProperty<Quaternion>(_reflex, "LastCommandStartRotation");
            RestoreNpcPose(baselinePosition, baselineRotation);

            float commandTime = ReadProperty<float>(_reflex, "LastCommandTime");
            Invoke(_observer, "TickObservation", commandTime + 0.01f);
            Assert.That(ReadProperty<int>(_observer, "VisibleMotionCount"), Is.Zero);
            Assert.That(ReadProperty<bool>(_observer, "IsAwaitingVisibleMotion"), Is.True);

            RestoreNpcPose(
                baselinePosition + Vector3.right * 0.005f,
                Quaternion.AngleAxis(0.5f, Vector3.up) * baselineRotation);
            Invoke(_observer, "TickObservation", commandTime + 0.02f);
            Assert.That(ReadProperty<int>(_observer, "VisibleMotionCount"), Is.Zero);
            Assert.That(ReadProperty<bool>(_observer, "IsAwaitingVisibleMotion"), Is.True);

            RestoreNpcPose(
                baselinePosition + Vector3.right * 0.011f,
                Quaternion.AngleAxis(0.5f, Vector3.up) * baselineRotation);
            Invoke(_observer, "TickObservation", commandTime + 0.03f);
            Assert.That(ReadProperty<int>(_observer, "VisibleMotionCount"), Is.EqualTo(1));
            Assert.That(ReadProperty<string>(_observer, "LastSignal"), Is.EqualTo("root_position"));
        }

        [Test]
        public void RotationOnlyThresholdProducesMeasuredRotationSignal()
        {
            Assert.That(
                InvokeResult<bool>(_reflex, "TryCommandFlinchStepBack", 6, 20f),
                Is.True);
            Vector3 baselinePosition = ReadProperty<Vector3>(_reflex, "LastCommandStartPosition");
            Quaternion baselineRotation = ReadProperty<Quaternion>(_reflex, "LastCommandStartRotation");
            RestoreNpcPose(
                baselinePosition,
                Quaternion.AngleAxis(1.1f, Vector3.up) * baselineRotation);

            float commandTime = ReadProperty<float>(_reflex, "LastCommandTime");
            Invoke(_observer, "TickObservation", commandTime + 0.01f);

            Assert.That(ReadProperty<int>(_observer, "VisibleMotionCount"), Is.EqualTo(1));
            Assert.That(ReadProperty<string>(_observer, "LastSignal"), Is.EqualTo("root_rotation"));
            Assert.That(ReadProperty<float>(_observer, "LastPositionDelta"), Is.LessThan(0.001f));
            Assert.That(ReadProperty<float>(_observer, "LastRotationDelta"), Is.GreaterThanOrEqualTo(1f));
        }

        [Test]
        public void DuplicateAndLaterEpisodesProduceAtMostOneObservationEach()
        {
            Assert.That(
                InvokeResult<bool>(_reflex, "TryCommandFlinchStepBack", 7, 30f),
                Is.True);
            float firstCommandTime = ReadProperty<float>(_reflex, "LastCommandTime");
            Invoke(_observer, "TickObservation", firstCommandTime + 0.01f);
            Assert.That(ReadProperty<int>(_observer, "VisibleMotionCount"), Is.EqualTo(1));

            Assert.That(
                InvokeResult<bool>(_reflex, "TryCommandFlinchStepBack", 7, 31f),
                Is.False);
            Invoke(_observer, "TickObservation", firstCommandTime + 1f);
            Assert.That(ReadProperty<int>(_observer, "VisibleMotionCount"), Is.EqualTo(1));

            Assert.That(
                InvokeResult<bool>(_reflex, "TryCommandFlinchStepBack", 8, 32f),
                Is.True);
            float secondCommandTime = ReadProperty<float>(_reflex, "LastCommandTime");
            Invoke(_observer, "TickObservation", secondCommandTime + 0.01f);
            Assert.That(ReadProperty<int>(_observer, "VisibleMotionCount"), Is.EqualTo(2));
            Assert.That(ReadProperty<int>(_observer, "LastObservedThreatEpisodeId"), Is.EqualTo(8));
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

        private void ConfirmCurrentThreat()
        {
            Invoke(_perception, "TickPerception", 1f / 12f);
            Assert.That(ReadProperty<object>(_perception, "State").ToString(), Is.EqualTo("Orienting"));
            Invoke(_perception, "TickOrientation", 0f);
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

        private void RestoreNpcPose(Vector3 position, Quaternion rotation)
        {
            CharacterController characterController = _npc.GetComponent<CharacterController>();
            characterController.enabled = false;
            _npc.transform.SetPositionAndRotation(position, rotation);
            characterController.enabled = true;
            Physics.SyncTransforms();
        }

        private void AssertReadOnlyProperty(string propertyName, Type propertyType)
        {
            PropertyInfo property = _observerType.GetProperty(
                propertyName,
                BindingFlags.Instance | BindingFlags.Public);
            Assert.That(property, Is.Not.Null);
            Assert.That(property.PropertyType, Is.EqualTo(propertyType));
            Assert.That(property.CanRead, Is.True);
            Assert.That(property.GetSetMethod(false), Is.Null);
        }

        private static string ReadConstant(Type type, string fieldName)
        {
            FieldInfo field = type.GetField(fieldName, BindingFlags.Static | BindingFlags.Public);
            Assert.That(field, Is.Not.Null);
            return (string)field.GetRawConstantValue();
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
