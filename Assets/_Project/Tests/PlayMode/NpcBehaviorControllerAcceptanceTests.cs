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
    public sealed class NpcBehaviorControllerAcceptanceTests
    {
        private const string ControllerTypeName = "QuickDraw.Core.SimpleFPSController, Assembly-CSharp";
        private const string EmitterTypeName = "QuickDraw.AI.Stimuli.AimThreatEmitter, Assembly-CSharp";
        private const string PerceptionTypeName = "QuickDraw.AI.Perception.SoftFOVPerception, Assembly-CSharp";
        private const string PatrolTypeName = "QuickDraw.AI.Activity.PatrolActivity, Assembly-CSharp";
        private const string BehaviorTypeName = "QuickDraw.AI.Behavior.NpcBehaviorController, Assembly-CSharp";
        private const string OutcomeTypeName = "QuickDraw.AI.Behavior.ActivityInterruptionOutcome, Assembly-CSharp";
        private const string ReflexTypeName = "QuickDraw.AI.Reflex.ReflexSelector, Assembly-CSharp";
        private const string ExpectedReason = "ConfirmedAimThreat";

        private Type _controllerType;
        private Type _emitterType;
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
            _emitterType = RequireType(EmitterTypeName);
            _perceptionType = RequireType(PerceptionTypeName);
            _patrolType = RequireType(PatrolTypeName);
            _behaviorType = RequireType(BehaviorTypeName);
            _reflexType = RequireType(ReflexTypeName);
            _player = RequireObject("Player");
            _npc = RequireObject("NPC_01");
            _sourceCamera = _player.GetComponentInChildren<Camera>(true);
            _controller = _player.GetComponent(_controllerType);
            _emitter = _player.GetComponent(_emitterType);
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
        public void SceneContainsConfiguredInterruptionCoordinatorContract()
        {
            Type outcomeType = RequireType(OutcomeTypeName);

            Assert.That(_behaviorType.IsSealed, Is.True);
            Assert.That(typeof(MonoBehaviour).IsAssignableFrom(_behaviorType), Is.True);
            Assert.That(
                UnityEngine.Object.FindObjectsByType(
                    _behaviorType,
                    FindObjectsInactive.Include,
                    FindObjectsSortMode.None),
                Has.Length.EqualTo(1));
            Assert.That(ReadPrivateField<Component>(_behavior, "perception"), Is.SameAs(_perception));
            Assert.That(ReadPrivateField<Component>(_behavior, "patrolActivity"), Is.SameAs(_patrol));
            Assert.That(ReadPrivateField<Component>(_behavior, "reflexSelector"), Is.SameAs(_reflex));
            Assert.That(Enum.GetNames(outcomeType), Is.EqualTo(new[] { "None", "Suspended", "Cancelled" }));

            AssertReadOnlyProperty("InterruptionCount", typeof(int));
            AssertReadOnlyProperty("LastHandledThreatEpisodeId", typeof(int));
            AssertReadOnlyProperty("InterruptedActivityName", typeof(string));
            AssertReadOnlyProperty("InterruptionReason", typeof(string));
            AssertReadOnlyProperty("InterruptionTime", typeof(float));
            AssertReadOnlyProperty("InterruptionOutcome", outcomeType);
            Assert.That(_behaviorType.GetEvent("ActivityInterrupted"), Is.Not.Null);

            string[] dependencies = _behaviorType
                .GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
                .Select(field => $"{field.Name} {field.FieldType.FullName}")
                .ToArray();
            Assert.That(dependencies, Has.None.Contains("Logging"));
            Assert.That(ReadProperty<int>(_behavior, "InterruptionCount"), Is.Zero);
            Assert.That(ReadProperty<string>(_behavior, "InterruptedActivityName"), Is.Empty);
            Assert.That(ReadProperty<float>(_behavior, "InterruptionTime"), Is.EqualTo(-1f));
        }

        [Test]
        public void ConfirmedThreatInterruptsPatrolAndRecordsSuspension()
        {
            Vector3 positionBeforePatrolTick = _npc.transform.position;
            Invoke(_patrol, "TickActivity", 0.25f);
            Assert.That(_npc.transform.position, Is.Not.EqualTo(positionBeforePatrolTick));
            ConfigureFrontalAim(10f);

            ConfirmCurrentThreat();

            float confirmationTime = ReadProperty<float>(_perception, "LastConfirmationTime");
            float interruptionTime = ReadProperty<float>(_behavior, "InterruptionTime");
            Assert.That(ReadProperty<bool>(_patrol, "IsRunning"), Is.False);
            Assert.That(ReadProperty<bool>(_patrol, "IsInterrupted"), Is.True);
            Assert.That(ReadProperty<bool>(_patrol, "IsCancelled"), Is.False);
            Assert.That(ReadProperty<string>(_patrol, "InterruptionReason"), Is.EqualTo(ExpectedReason));
            Assert.That(ReadProperty<int>(_behavior, "InterruptionCount"), Is.EqualTo(1));
            Assert.That(ReadProperty<int>(_behavior, "LastHandledThreatEpisodeId"), Is.EqualTo(1));
            Assert.That(ReadProperty<string>(_behavior, "InterruptedActivityName"), Is.EqualTo("Patrol"));
            Assert.That(ReadProperty<string>(_behavior, "InterruptionReason"), Is.EqualTo(ExpectedReason));
            Assert.That(ReadProperty<object>(_behavior, "InterruptionOutcome").ToString(), Is.EqualTo("Suspended"));
            Assert.That(interruptionTime, Is.EqualTo(ReadProperty<float>(_patrol, "InterruptionTime")));
            Assert.That(interruptionTime, Is.GreaterThanOrEqualTo(confirmationTime));

            Vector3 interruptedPosition = _npc.transform.position;
            Invoke(_patrol, "TickActivity", 1f);
            Assert.That(_npc.transform.position, Is.EqualTo(interruptedPosition));
        }

        [Test]
        public void SameEpisodeDoesNotRepeatButARearmedEpisodeInterruptsAgain()
        {
            ConfigureFrontalAim(20f);
            ConfirmCurrentThreat();
            float firstInterruptionTime = ReadProperty<float>(_behavior, "InterruptionTime");
            Assert.That(ReadProperty<int>(_reflex, "CommandCount"), Is.EqualTo(1));

            Invoke(_behavior, "HandleThreatConfirmed", _perception);
            Invoke(_behavior, "HandleThreatConfirmed", _perception);
            for (int i = 0; i < 5; i++)
            {
                Invoke(_perception, "TickPerception", 1f / 12f);
                Invoke(_perception, "TickOrientation", 1f / 60f);
            }

            Assert.That(ReadProperty<int>(_behavior, "InterruptionCount"), Is.EqualTo(1));
            Assert.That(ReadProperty<int>(_reflex, "CommandCount"), Is.EqualTo(1));
            Assert.That(ReadProperty<float>(_behavior, "InterruptionTime"), Is.EqualTo(firstInterruptionTime));
            Assert.That(ReadProperty<int>(_perception, "ThreatEpisodeId"), Is.EqualTo(1));

            SetAiming(false, 21f);
            Invoke(_perception, "TickPerception", 1f);
            Assert.That(ReadProperty<object>(_perception, "State").ToString(), Is.EqualTo("Idle"));
            Invoke(_patrol, "ResumeActivity");
            Assert.That(ReadProperty<bool>(_patrol, "IsRunning"), Is.True);

            SetAiming(true, 22f);
            ConfirmCurrentThreat();

            Assert.That(ReadProperty<int>(_perception, "ThreatEpisodeId"), Is.EqualTo(2));
            Assert.That(ReadProperty<int>(_behavior, "InterruptionCount"), Is.EqualTo(2));
            Assert.That(ReadProperty<int>(_behavior, "LastHandledThreatEpisodeId"), Is.EqualTo(2));
            Assert.That(ReadProperty<int>(_reflex, "CommandCount"), Is.EqualTo(2));
            Assert.That(ReadProperty<int>(_reflex, "LastCommandedThreatEpisodeId"), Is.EqualTo(2));
            Assert.That(ReadProperty<bool>(_patrol, "IsRunning"), Is.False);
            Assert.That(ReadProperty<bool>(_patrol, "IsInterrupted"), Is.True);
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

        private void AssertReadOnlyProperty(string propertyName, Type propertyType)
        {
            PropertyInfo property = _behaviorType.GetProperty(
                propertyName,
                BindingFlags.Instance | BindingFlags.Public);
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
    }
}
