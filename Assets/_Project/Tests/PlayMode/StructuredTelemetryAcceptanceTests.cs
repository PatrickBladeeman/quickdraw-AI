using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text.RegularExpressions;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

namespace QuickDraw.Tests.PlayMode
{
    public sealed class StructuredTelemetryAcceptanceTests
    {
        private const string LoggerTypeName = "QuickDraw.Logging.JsonlLogger, Assembly-CSharp";
        private const string RecorderTypeName = "QuickDraw.Logging.TelemetryRecorder, Assembly-CSharp";
        private const string ControllerTypeName = "QuickDraw.Core.SimpleFPSController, Assembly-CSharp";
        private const string EmitterTypeName = "QuickDraw.AI.Stimuli.AimThreatEmitter, Assembly-CSharp";
        private const string PerceptionTypeName = "QuickDraw.AI.Perception.SoftFOVPerception, Assembly-CSharp";
        private const string PatrolTypeName = "QuickDraw.AI.Activity.PatrolActivity, Assembly-CSharp";
        private const string BehaviorTypeName = "QuickDraw.AI.Behavior.NpcBehaviorController, Assembly-CSharp";
        private const string ReflexTypeName = "QuickDraw.AI.Reflex.ReflexSelector, Assembly-CSharp";
        private const string ObserverTypeName = "QuickDraw.AI.Reflex.VisibleMotionObserver, Assembly-CSharp";

        private Type _loggerType;
        private Type _recorderType;
        private Component _logger;
        private Component _recorder;
        private string _temporaryDirectory;

        [UnitySetUp]
        public IEnumerator SetUpScene()
        {
            SceneManager.LoadScene("Test_Arena", LoadSceneMode.Single);
            yield return null;

            _loggerType = RequireType(LoggerTypeName);
            _recorderType = RequireType(RecorderTypeName);
            GameObject systems = RequireObject("Systems");
            _logger = systems.GetComponent(_loggerType);
            _recorder = systems.GetComponent(_recorderType);
            Assert.That(_logger, Is.Not.Null);
            Assert.That(_recorder, Is.Not.Null);

            _temporaryDirectory = Path.Combine(
                Application.temporaryCachePath,
                $"quickdraw-task8b-{Guid.NewGuid():N}");
            Invoke(_logger, "ConfigureOutput", _temporaryDirectory, false);
            Invoke(_logger, "ResetSessionState");
            Invoke(_recorder, "ResetRecordingState");
        }

        [UnityTearDown]
        public IEnumerator TearDownScene()
        {
            Invoke(_logger, "ConfigureOutput", _temporaryDirectory, false);
            if (Directory.Exists(_temporaryDirectory))
            {
                Directory.Delete(_temporaryDirectory, true);
            }

            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
            yield return null;
        }

        [Test]
        public void SceneContainsDomainReloadSafeObserverOnlyTelemetryContract()
        {
            Assert.That(_loggerType.IsSealed, Is.True);
            Assert.That(_recorderType.IsSealed, Is.True);
            Assert.That(ReadStaticProperty<Component>(_loggerType, "Instance"), Is.SameAs(_logger));
            Assert.That(_loggerType.GetMethod("Record"), Is.Not.Null);
            Assert.That(_loggerType.GetMethod("ProcessPendingNow"), Is.Not.Null);
            Assert.That(_loggerType.GetMethod("FlushNow"), Is.Not.Null);
            Assert.That(_loggerType.GetMethod("GetLatencySummary"), Is.Not.Null);

            MethodInfo resetStatic = _loggerType.GetMethod(
                "ResetStaticState",
                BindingFlags.Static | BindingFlags.NonPublic);
            Assert.That(resetStatic, Is.Not.Null);
            Assert.That(
                resetStatic.GetCustomAttributes(false)
                    .Any(attribute => attribute.GetType().Name == "RuntimeInitializeOnLoadMethodAttribute"),
                Is.True);

            Assert.That(ReadPrivateField<Component>(_recorder, "logger"), Is.SameAs(_logger));
            Assert.That(ReadPrivateField<Component>(_recorder, "aimThreatEmitter"), Is.Not.Null);
            Assert.That(ReadPrivateField<Component>(_recorder, "perception"), Is.Not.Null);
            Assert.That(ReadPrivateField<Component>(_recorder, "patrolActivity"), Is.Not.Null);
            Assert.That(ReadPrivateField<Component>(_recorder, "behaviorController"), Is.Not.Null);
            Assert.That(ReadPrivateField<Component>(_recorder, "reflexSelector"), Is.Not.Null);
            Assert.That(ReadPrivateField<Component>(_recorder, "visibleMotionObserver"), Is.Not.Null);

            foreach (string typeName in new[]
            {
                EmitterTypeName,
                PerceptionTypeName,
                PatrolTypeName,
                BehaviorTypeName,
                ReflexTypeName,
                ObserverTypeName
            })
            {
                string[] dependencies = RequireType(typeName)
                    .GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
                    .Select(field => field.FieldType.FullName ?? string.Empty)
                    .ToArray();
                Assert.That(dependencies, Has.None.Contains("QuickDraw.Logging"));
            }

            Type patrolType = RequireType(PatrolTypeName);
            Assert.That(patrolType.GetEvent("ActivityStarted"), Is.Not.Null);
            Assert.That(patrolType.GetEvent("ActivityInterrupted"), Is.Not.Null);
            Assert.That(patrolType.GetEvent("ActivityResumed"), Is.Not.Null);
            Assert.That(patrolType.GetEvent("ActivityCancelled"), Is.Not.Null);
        }

        [Test]
        public void TypedRecordsSerializeAsValidPopulatedJson()
        {
            object record = CreateRecord(
                "ThreatConfirmedEventRecord",
                2.5f,
                "NPC_01",
                7,
                18.25f);

            Record(record);
            Assert.That(ReadProperty<int>(_logger, "PendingCount"), Is.EqualTo(2));
            Assert.That(ReadProperty<int>(_logger, "BufferedLineCount"), Is.Zero);

            Invoke(_logger, "ProcessPendingNow");
            string[] lines = GetBufferedLines();

            Assert.That(lines, Has.Length.EqualTo(2));
            Assert.That(lines[1], Does.Contain("\"t\":\"threat_confirmed\""));
            Assert.That(lines[1], Does.Contain("\"npcId\":\"NPC_01\""));
            Assert.That(lines[1], Does.Contain("\"episodeId\":7"));
            Assert.That(lines[1], Does.Contain("\"turn_to_confirmation_ms\":18.25"));
            Assert.That(lines[1], Is.Not.EqualTo("{}"));

            Type jsonConvertType = RequireType("Newtonsoft.Json.JsonConvert, Newtonsoft.Json");
            MethodInfo deserialize = jsonConvertType
                .GetMethods(BindingFlags.Static | BindingFlags.Public)
                .Single(method =>
                    method.Name == "DeserializeObject" &&
                    !method.IsGenericMethod &&
                    method.GetParameters().Length == 1 &&
                    method.GetParameters()[0].ParameterType == typeof(string));
            Assert.That(deserialize, Is.Not.Null);
            Assert.DoesNotThrow(() => deserialize.Invoke(null, new object[] { lines[1] }));
        }

        [Test]
        public void EventsStayBufferedUntilAnExplicitSuccessfulFlush()
        {
            Invoke(_logger, "ConfigureOutput", _temporaryDirectory, true);
            Invoke(_logger, "ResetSessionState");
            string logPath = ReadProperty<string>(_logger, "CurrentLogPath");
            Record(CreateRecord(
                "AimStimulusEventRecord",
                "aim_stimulus_started",
                1f,
                42,
                30f));

            Assert.That(File.Exists(logPath), Is.False);
            Invoke(_logger, "ProcessPendingNow");
            Assert.That(File.Exists(logPath), Is.False);
            Assert.That(ReadProperty<int>(_logger, "BufferedLineCount"), Is.EqualTo(2));

            bool flushed = InvokeWithResult<bool>(_logger, "FlushNow");

            Assert.That(flushed, Is.True);
            Assert.That(File.Exists(logPath), Is.True);
            Assert.That(File.ReadAllLines(logPath), Has.Length.EqualTo(2));
            Assert.That(ReadProperty<int>(_logger, "BufferedLineCount"), Is.Zero);
            Assert.That(ReadProperty<int>(_logger, "WrittenLineCount"), Is.EqualTo(2));
        }

        [Test]
        public void FullRuntimePipelineRecordsOrderedCommandAndVisibleOnsetEvents()
        {
            Type controllerType = RequireType(ControllerTypeName);
            Type emitterType = RequireType(EmitterTypeName);
            Type perceptionType = RequireType(PerceptionTypeName);
            Type patrolType = RequireType(PatrolTypeName);
            Type behaviorType = RequireType(BehaviorTypeName);
            Type reflexType = RequireType(ReflexTypeName);
            Type observerType = RequireType(ObserverTypeName);
            GameObject player = RequireObject("Player");
            GameObject npc = RequireObject("NPC_01");
            Component controller = player.GetComponent(controllerType);
            Component emitter = player.GetComponent(emitterType);
            Component perception = npc.GetComponent(perceptionType);
            Component patrol = npc.GetComponent(patrolType);
            Component behavior = npc.GetComponent(behaviorType);
            Component observer = npc.GetComponent(observerType);

            ((Behaviour)controller).enabled = false;
            ((Behaviour)emitter).enabled = false;
            ((Behaviour)perception).enabled = false;
            ((Behaviour)patrol).enabled = false;
            Invoke(perception, "ResetPerception");
            Invoke(patrol, "ResetActivity");
            Invoke(behavior, "ResetCoordination");
            Invoke(observer, "ResetObservation");
            Invoke(_logger, "ResetSessionState");
            Invoke(_recorder, "ResetRecordingState");
            Invoke(_recorder, "RecordInitialActivityIfNeeded");

            Camera sourceCamera = player.GetComponentInChildren<Camera>(true);
            Vector3 playerPosition = npc.transform.position + npc.transform.forward * 5f;
            player.transform.position = playerPosition;
            Transform pivot = player.transform.Find("CameraPivot");
            if (pivot != null)
            {
                pivot.localRotation = Quaternion.identity;
            }

            Physics.SyncTransforms();
            Vector3 target = npc.GetComponent<CharacterController>().bounds.center;
            sourceCamera.transform.rotation = Quaternion.LookRotation(
                (target - sourceCamera.transform.position).normalized,
                Vector3.up);
            Physics.SyncTransforms();

            float stimulusTime = Time.realtimeSinceStartup;
            SetAiming(controller, true);
            Invoke(emitter, "RefreshStimulus", stimulusTime);
            Invoke(perception, "TickPerception", 1f / 12f);
            Invoke(perception, "TickOrientation", 0f);
            Invoke(observer, "TickObservation", Time.realtimeSinceStartup);

            SetAiming(controller, false);
            Invoke(emitter, "RefreshStimulus", Time.realtimeSinceStartup);
            Invoke(perception, "TickPerception", 0.1f);
            Invoke(patrol, "ResumeActivity");

            SetAiming(controller, true);
            Invoke(emitter, "RefreshStimulus", Time.realtimeSinceStartup);
            Invoke(perception, "TickPerception", 1f / 12f);
            SetAiming(controller, false);
            Invoke(emitter, "RefreshStimulus", Time.realtimeSinceStartup);
            Invoke(perception, "TickPerception", 0.1f);
            Invoke(_logger, "ProcessPendingNow");

            string[] eventTypes = GetBufferedLines()
                .Select(ReadEventType)
                .ToArray();
            string[] expectedOrder =
            {
                "session_start",
                "activity_started",
                "aim_stimulus_started",
                "perception_notice",
                "suspicion_threshold",
                "turn_started",
                "threat_confirmed",
                "activity_interrupted",
                "reflex_commanded",
                "visible_motion_started",
                "aim_stimulus_ended",
                "threat_released",
                "activity_resumed"
            };

            AssertOrderedSubsequence(eventTypes, expectedOrder);
            Assert.That(eventTypes.Count(value => value == "reflex_commanded"), Is.EqualTo(1));
            Assert.That(eventTypes.Count(value => value == "visible_motion_started"), Is.EqualTo(1));
            Assert.That(eventTypes.Count(value => value == "threat_confirmed"), Is.EqualTo(1),
                "Re-aiming during the same episode must not fabricate a second confirmation.");
            Assert.That(eventTypes.Count(value => value == "threat_released"), Is.EqualTo(1),
                "Repeated release transitions in one episode must not fabricate another release edge.");
            Assert.That(ReadProperty<bool>(patrol, "IsRunning"), Is.True);
        }

        [Test]
        public void LatencySummariesIncludeRequiredDescriptiveStatistics()
        {
            foreach (float sample in new[] { 10f, 20f, 30f, 40f })
            {
                Record(CreateRecord(
                    "PerceptionNoticeEventRecord",
                    sample / 1000f,
                    "NPC_01",
                    45f,
                    true,
                    sample));
            }

            Invoke(_logger, "ProcessPendingNow");
            object summary = InvokeWithResult<object>(
                _logger,
                "GetLatencySummary",
                "stimulus_to_notice");

            Assert.That(ReadProperty<int>(summary, "Count"), Is.EqualTo(4));
            Assert.That(ReadProperty<float>(summary, "Minimum"), Is.EqualTo(10f));
            Assert.That(ReadProperty<float>(summary, "Maximum"), Is.EqualTo(40f));
            Assert.That(ReadProperty<float>(summary, "Mean"), Is.EqualTo(25f));
            Assert.That(ReadProperty<float>(summary, "P50"), Is.EqualTo(20f));
            Assert.That(ReadProperty<float>(summary, "P95"), Is.EqualTo(40f));
            Assert.That(ReadProperty<float>(summary, "StandardDeviation"), Is.EqualTo(11.18034f).Within(0.001f));

            Invoke(_logger, "QueueSummaryRecords");
            Invoke(_logger, "ProcessPendingNow");
            string[] lines = GetBufferedLines();
            Assert.That(lines, Has.Some.Contains("\"t\":\"session_summary\""));
            Assert.That(lines, Has.Some.Contains("\"stage\":\"stimulus_to_notice\""));
            Assert.That(lines, Has.Some.Contains("\"stddev_ms\":"));
        }

        [Test]
        public void FlushFailureIsContainedAndNpcActivityStillTransitions()
        {
            Directory.CreateDirectory(_temporaryDirectory);
            string blockingFile = Path.Combine(_temporaryDirectory, "not-a-directory");
            File.WriteAllText(blockingFile, "blocking file");
            Invoke(_logger, "ConfigureOutput", blockingFile, true);
            Invoke(_logger, "ResetSessionState");
            Invoke(_logger, "ProcessPendingNow");

            LogAssert.Expect(LogType.Warning, new Regex("JSONL telemetry flush failed:"));
            bool flushed = true;
            Assert.DoesNotThrow(() => flushed = InvokeWithResult<bool>(_logger, "FlushNow"));
            Assert.That(flushed, Is.False);
            Assert.That(ReadProperty<int>(_logger, "FailedFlushCount"), Is.EqualTo(1));
            Assert.That(ReadProperty<string>(_logger, "LastError"), Is.Not.Empty);
            Assert.That(ReadProperty<int>(_logger, "BufferedLineCount"), Is.EqualTo(1));

            Component patrol = RequireObject("NPC_01").GetComponent(RequireType(PatrolTypeName));
            Assert.DoesNotThrow(() => Invoke(patrol, "InterruptActivity", "TelemetryFailureTest"));
            Assert.That(ReadProperty<bool>(patrol, "IsInterrupted"), Is.True);
            Assert.DoesNotThrow(() => Invoke(patrol, "ResumeActivity"));
            Assert.That(ReadProperty<bool>(patrol, "IsRunning"), Is.True);
        }

        private void Record(object eventRecord)
        {
            MethodInfo recordMethod = _loggerType.GetMethod("Record");
            Assert.That(recordMethod, Is.Not.Null);
            recordMethod.Invoke(_logger, new[] { eventRecord });
        }

        private static object CreateRecord(string shortTypeName, params object[] arguments)
        {
            Type recordType = RequireType($"QuickDraw.Logging.{shortTypeName}, Assembly-CSharp");
            object result = Activator.CreateInstance(recordType, arguments);
            Assert.That(result, Is.Not.Null);
            return result;
        }

        private string[] GetBufferedLines()
        {
            return InvokeWithResult<string[]>(_logger, "GetBufferedLinesSnapshot");
        }

        private static string ReadEventType(string json)
        {
            Match match = Regex.Match(json, "\\\"t\\\":\\\"([^\\\"]+)\\\"");
            Assert.That(match.Success, Is.True, $"Missing event type in {json}.");
            return match.Groups[1].Value;
        }

        private static void AssertOrderedSubsequence(
            IReadOnlyList<string> actual,
            IReadOnlyList<string> expected)
        {
            int searchStart = 0;
            foreach (string expectedValue in expected)
            {
                int foundIndex = -1;
                for (int index = searchStart; index < actual.Count; index++)
                {
                    if (actual[index] == expectedValue)
                    {
                        foundIndex = index;
                        break;
                    }
                }

                Assert.That(foundIndex, Is.GreaterThanOrEqualTo(0),
                    $"Missing ordered event {expectedValue}. Actual: {string.Join(", ", actual)}");
                searchStart = foundIndex + 1;
            }
        }

        private static void SetAiming(object controller, bool isAiming)
        {
            PropertyInfo property = controller.GetType().GetProperty(
                "IsAiming",
                BindingFlags.Instance | BindingFlags.Public);
            MethodInfo setter = property?.GetSetMethod(true);
            Assert.That(setter, Is.Not.Null);
            setter.Invoke(controller, new object[] { isAiming });
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

        private static T ReadStaticProperty<T>(Type type, string propertyName)
        {
            PropertyInfo property = type.GetProperty(
                propertyName,
                BindingFlags.Static | BindingFlags.Public);
            Assert.That(property, Is.Not.Null, $"Missing property {propertyName}.");
            return (T)property.GetValue(null);
        }

        private static void Invoke(object instance, string methodName, params object[] arguments)
        {
            MethodInfo method = ResolveMethod(instance, methodName, arguments);
            Assert.That(method, Is.Not.Null, $"Missing method {methodName}.");
            method.Invoke(instance, arguments);
        }

        private static T InvokeWithResult<T>(
            object instance,
            string methodName,
            params object[] arguments)
        {
            MethodInfo method = ResolveMethod(instance, methodName, arguments);
            Assert.That(method, Is.Not.Null, $"Missing method {methodName}.");
            return (T)method.Invoke(instance, arguments);
        }

        private static MethodInfo ResolveMethod(
            object instance,
            string methodName,
            IReadOnlyList<object> arguments)
        {
            return instance.GetType()
                .GetMethods(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
                .SingleOrDefault(method =>
                {
                    if (method.Name != methodName)
                    {
                        return false;
                    }

                    ParameterInfo[] parameters = method.GetParameters();
                    if (parameters.Length != arguments.Count)
                    {
                        return false;
                    }

                    for (int index = 0; index < parameters.Length; index++)
                    {
                        object argument = arguments[index];
                        if (argument != null &&
                            !parameters[index].ParameterType.IsInstanceOfType(argument))
                        {
                            return false;
                        }
                    }

                    return true;
                });
        }
    }
}
