using System;
using System.Collections;
using System.Linq;
using System.Linq.Expressions;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

namespace QuickDraw.Tests.PlayMode
{
    public sealed class AimThreatEmitterAcceptanceTests : InputTestFixture
    {
        private const string ControllerTypeName = "QuickDraw.Core.SimpleFPSController, Assembly-CSharp";
        private const string EmitterTypeName = "QuickDraw.AI.Stimuli.AimThreatEmitter, Assembly-CSharp";
        private const string StimulusTypeName = "QuickDraw.AI.Stimuli.AimThreatStimulus, Assembly-CSharp";
        private const string PatrolTypeName = "QuickDraw.AI.Activity.PatrolActivity, Assembly-CSharp";
        private const string ReflexTypeName = "QuickDraw.AI.Reflex.ReflexSelector, Assembly-CSharp";

        private int _startCount;
        private int _endCount;
        private object _lastStartStimulus;
        private object _lastEndStimulus;

        [UnitySetUp]
        public IEnumerator SetUpScene()
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
        public void SceneContainsConfiguredCameraBackedEmitterAndPlainStimulusContract()
        {
            Type controllerType = RequireType(ControllerTypeName);
            Type emitterType = RequireType(EmitterTypeName);
            Type stimulusType = RequireType(StimulusTypeName);
            GameObject player = GameObject.Find("Player");

            Assert.That(player, Is.Not.Null);
            Assert.That(emitterType.IsSealed, Is.True);
            Assert.That(typeof(MonoBehaviour).IsAssignableFrom(emitterType), Is.True);
            Assert.That(stimulusType.IsValueType, Is.True);
            Assert.That(stimulusType.IsSerializable, Is.True);

            AssertFieldContract(stimulusType, "SourceId", typeof(int));
            AssertFieldContract(stimulusType, "Origin", typeof(Vector3));
            AssertFieldContract(stimulusType, "Direction", typeof(Vector3));
            AssertFieldContract(stimulusType, "Timestamp", typeof(float));
            AssertFieldContract(stimulusType, "MaxDistance", typeof(float));
            AssertFieldContract(stimulusType, "IsAiming", typeof(bool));
            Assert.That(
                stimulusType.GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.DeclaredOnly),
                Has.Length.EqualTo(6));

            Component controller = player.GetComponent(controllerType);
            Component emitter = player.GetComponent(emitterType);
            Camera sourceCamera = player.GetComponentInChildren<Camera>(true);

            Assert.That(controller, Is.Not.Null);
            Assert.That(emitter, Is.Not.Null);
            Assert.That(sourceCamera, Is.Not.Null);
            Assert.That(UnityEngine.Object.FindObjectsByType(emitterType, FindObjectsInactive.Include, FindObjectsSortMode.None), Has.Length.EqualTo(1));
            Assert.That(ReadPrivateField<Component>(emitter, "controller"), Is.SameAs(controller));
            Assert.That(ReadPrivateField<Camera>(emitter, "sourceCamera"), Is.SameAs(sourceCamera));
            Assert.That(ReadPrivateField<float>(emitter, "maxDistance"), Is.EqualTo(30f));

            PropertyInfo currentProperty = emitterType.GetProperty("CurrentStimulus", BindingFlags.Instance | BindingFlags.Public);
            Assert.That(currentProperty, Is.Not.Null);
            Assert.That(currentProperty.PropertyType, Is.EqualTo(stimulusType));
            Assert.That(currentProperty.CanRead, Is.True);
            Assert.That(currentProperty.GetSetMethod(false), Is.Null);
            Assert.That(emitterType.GetEvent("AimStarted"), Is.Not.Null);
            Assert.That(emitterType.GetEvent("AimEnded"), Is.Not.Null);

            ((Behaviour)controller).enabled = false;
            ((Behaviour)emitter).enabled = false;
            SetAiming(controller, false);
            InvokePrivate(emitter, "RefreshStimulus", 123.5f);

            object stimulus = currentProperty.GetValue(emitter);
            Assert.That(ReadPublicField<int>(stimulus, "SourceId"), Is.EqualTo(player.GetInstanceID()));
            Assert.That(ReadPublicField<Vector3>(stimulus, "Origin"), Is.EqualTo(sourceCamera.transform.position));
            Assert.That(ReadPublicField<Vector3>(stimulus, "Direction"), Is.EqualTo(sourceCamera.transform.forward.normalized));
            Assert.That(ReadPublicField<float>(stimulus, "Timestamp"), Is.EqualTo(123.5f));
            Assert.That(ReadPublicField<float>(stimulus, "MaxDistance"), Is.EqualTo(30f));
            Assert.That(ReadPublicField<bool>(stimulus, "IsAiming"), Is.False);

            string[] dependencyNames = emitterType
                .GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
                .Select(field => $"{field.Name} {field.FieldType.FullName}")
                .ToArray();
            Assert.That(dependencyNames, Has.None.Contains("Reflex"));
            Assert.That(dependencyNames, Has.None.Contains("Perception"));
            Assert.That(dependencyNames, Has.None.Contains("bypass"));
        }

        [Test]
        public void RightMouseTransitionsPublishSingleStartAndEndEdgesWithoutChangingNpcActivity()
        {
            Type controllerType = RequireType(ControllerTypeName);
            Type emitterType = RequireType(EmitterTypeName);
            Type patrolType = RequireType(PatrolTypeName);
            Type reflexType = RequireType(ReflexTypeName);
            GameObject player = GameObject.Find("Player");
            GameObject npc = GameObject.Find("NPC_01");
            Component controller = player.GetComponent(controllerType);
            Component emitter = player.GetComponent(emitterType);
            Component patrol = npc.GetComponent(patrolType);
            Mouse mouse = InputSystem.AddDevice<Mouse>("Task5 Test Mouse");

            Assert.That(controller, Is.Not.Null);
            Assert.That(emitter, Is.Not.Null);
            Assert.That(patrol, Is.Not.Null);
            Assert.That(npc.GetComponent(reflexType), Is.Null, "Task 5 must not wire reflex selection directly.");

            ((Behaviour)controller).enabled = false;
            ((Behaviour)emitter).enabled = false;
            InvokePrivate(controller, "SetCursorLocked", true);

            EventInfo startedEvent = emitterType.GetEvent("AimStarted");
            EventInfo endedEvent = emitterType.GetEvent("AimEnded");
            Delegate startedHandler = BuildEventHandler(startedEvent, nameof(CaptureStart));
            Delegate endedHandler = BuildEventHandler(endedEvent, nameof(CaptureEnd));
            startedEvent.AddEventHandler(emitter, startedHandler);
            endedEvent.AddEventHandler(emitter, endedHandler);

            try
            {
                Vector3 npcPosition = npc.transform.position;
                InvokePrivate(controller, "Tick", null, mouse, 1f / 60f);
                InvokePrivate(emitter, "RefreshStimulus", 9f);
                Assert.That(_startCount, Is.Zero);
                Assert.That(_endCount, Is.Zero);

                Press(mouse.rightButton);
                InputSystem.Update();
                InvokePrivate(controller, "Tick", null, mouse, 1f / 60f);
                InvokePrivate(emitter, "RefreshStimulus", 10f);
                Assert.That(_startCount, Is.EqualTo(1));
                Assert.That(_endCount, Is.Zero);
                Assert.That(ReadPublicField<bool>(_lastStartStimulus, "IsAiming"), Is.True);
                Assert.That(ReadPublicField<float>(_lastStartStimulus, "Timestamp"), Is.EqualTo(10f));

                InvokePrivate(controller, "Tick", null, mouse, 1f / 60f);
                InvokePrivate(emitter, "RefreshStimulus", 11f);
                Assert.That(_startCount, Is.EqualTo(1), "Holding RMB must not repeat the start edge.");

                Release(mouse.rightButton);
                InputSystem.Update();
                InvokePrivate(controller, "Tick", null, mouse, 1f / 60f);
                InvokePrivate(emitter, "RefreshStimulus", 12f);
                Assert.That(_startCount, Is.EqualTo(1));
                Assert.That(_endCount, Is.EqualTo(1));
                Assert.That(ReadPublicField<bool>(_lastEndStimulus, "IsAiming"), Is.False);
                Assert.That(ReadPublicField<float>(_lastEndStimulus, "Timestamp"), Is.EqualTo(12f));

                InvokePrivate(emitter, "RefreshStimulus", 13f);
                Assert.That(_endCount, Is.EqualTo(1), "Released RMB must not repeat the end edge.");
                Assert.That(ReadPublicProperty<bool>(patrol, "IsRunning"), Is.True);
                Assert.That(npc.transform.position, Is.EqualTo(npcPosition));
            }
            finally
            {
                startedEvent.RemoveEventHandler(emitter, startedHandler);
                endedEvent.RemoveEventHandler(emitter, endedHandler);
            }
        }

        private Delegate BuildEventHandler(EventInfo eventInfo, string captureMethodName)
        {
            Assert.That(eventInfo, Is.Not.Null);
            Type stimulusType = eventInfo.EventHandlerType.GetGenericArguments()[0];
            ParameterExpression stimulus = Expression.Parameter(stimulusType, "stimulus");
            MethodInfo captureMethod = GetType().GetMethod(captureMethodName, BindingFlags.Instance | BindingFlags.NonPublic);
            MethodCallExpression captureCall = Expression.Call(
                Expression.Constant(this),
                captureMethod,
                Expression.Convert(stimulus, typeof(object)));
            return Expression.Lambda(eventInfo.EventHandlerType, captureCall, stimulus).Compile();
        }

        private void CaptureStart(object stimulus)
        {
            _startCount++;
            _lastStartStimulus = stimulus;
        }

        private void CaptureEnd(object stimulus)
        {
            _endCount++;
            _lastEndStimulus = stimulus;
        }

        private static Type RequireType(string qualifiedName)
        {
            Type type = Type.GetType(qualifiedName);
            Assert.That(type, Is.Not.Null, $"Could not find {qualifiedName}.");
            return type;
        }

        private static void AssertFieldContract(Type type, string fieldName, Type fieldType)
        {
            FieldInfo field = type.GetField(fieldName, BindingFlags.Instance | BindingFlags.Public);
            Assert.That(field, Is.Not.Null, $"Missing field {fieldName}.");
            Assert.That(field.FieldType, Is.EqualTo(fieldType));
        }

        private static T ReadPrivateField<T>(object instance, string fieldName)
        {
            FieldInfo field = instance.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
            Assert.That(field, Is.Not.Null, $"Missing field {fieldName}.");
            return (T)field.GetValue(instance);
        }

        private static T ReadPublicField<T>(object instance, string fieldName)
        {
            FieldInfo field = instance.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.Public);
            Assert.That(field, Is.Not.Null, $"Missing field {fieldName}.");
            return (T)field.GetValue(instance);
        }

        private static T ReadPublicProperty<T>(object instance, string propertyName)
        {
            PropertyInfo property = instance.GetType().GetProperty(propertyName, BindingFlags.Instance | BindingFlags.Public);
            Assert.That(property, Is.Not.Null, $"Missing property {propertyName}.");
            return (T)property.GetValue(instance);
        }

        private static void SetAiming(object controller, bool isAiming)
        {
            PropertyInfo property = controller.GetType().GetProperty("IsAiming", BindingFlags.Instance | BindingFlags.Public);
            MethodInfo setter = property?.GetSetMethod(true);
            Assert.That(setter, Is.Not.Null, "IsAiming must retain its private setter for controller ownership.");
            setter.Invoke(controller, new object[] { isAiming });
        }

        private static void InvokePrivate(object instance, string methodName, params object[] arguments)
        {
            MethodInfo method = instance.GetType().GetMethod(methodName, BindingFlags.Instance | BindingFlags.NonPublic);
            Assert.That(method, Is.Not.Null, $"Missing method {methodName}.");
            method.Invoke(instance, arguments);
        }
    }
}

