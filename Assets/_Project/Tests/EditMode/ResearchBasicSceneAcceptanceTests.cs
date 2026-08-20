using System;
using System.Linq;
using NUnit.Framework;
using QuickDraw.Research.Actuation;
using QuickDraw.Research.Basic;
using Unity.MLAgents;
using Unity.MLAgents.Policies;
using Unity.MLAgents.Sensors;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace QuickDraw.Tests.EditMode
{
    public sealed class ResearchBasicSceneAcceptanceTests
    {
        private const string ScenePath =
            "Assets/_Project/Scenes/Research_Basic.unity";

        [Test]
        public void DedicatedSceneMatchesTheFrozenBasicContract()
        {
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            ResearchBasicAgent agent =
                UnityEngine.Object.FindFirstObjectByType<ResearchBasicAgent>();
            ResearchBasicTarget target =
                UnityEngine.Object.FindFirstObjectByType<ResearchBasicTarget>();
            ResearchBasicActuator actuator = agent?.GetComponent<ResearchBasicActuator>();
            ResearchBasicVisualSensorComponent sensor =
                agent?.GetComponent<ResearchBasicVisualSensorComponent>();
            BehaviorParameters behavior = agent?.GetComponent<BehaviorParameters>();
            DecisionRequester requester = agent?.GetComponent<DecisionRequester>();

            Assert.That(agent, Is.Not.Null);
            Assert.That(target, Is.Not.Null);
            Assert.That(actuator, Is.Not.Null);
            Assert.That(sensor, Is.Not.Null);
            Assert.That(behavior, Is.Not.Null);
            Assert.That(requester, Is.Not.Null);
            Assert.That(agent.Actuator, Is.SameAs(actuator));
            Assert.That(agent.Target, Is.SameAs(target));
            Assert.That(agent.VisualSensor, Is.SameAs(sensor));
            Assert.That(agent.MaxStep, Is.Zero);
            Assert.That(
                agent.ScenarioSeed,
                Is.EqualTo(ResearchBasicContract.ScenarioSeed));

            Assert.That(
                behavior.BehaviorName,
                Is.EqualTo(ResearchBasicContract.BehaviorName));
            Assert.That(behavior.BehaviorType, Is.EqualTo(BehaviorType.Default));
            Assert.That(behavior.BrainParameters.VectorObservationSize, Is.Zero);
            CollectionAssert.AreEqual(
                new[]
                {
                    ResearchBasicContract.MovementBranchSize,
                    ResearchBasicContract.CombatBranchSize
                },
                behavior.BrainParameters.ActionSpec.BranchSizes);
            Assert.That(behavior.UseChildSensors, Is.True);
            Assert.That(behavior.UseChildActuators, Is.False);

            Assert.That(
                requester.DecisionPeriod,
                Is.EqualTo(ResearchBasicContract.DecisionPeriodFixedSteps));
            Assert.That(requester.DecisionStep, Is.Zero);
            Assert.That(requester.TakeActionsBetweenDecisions, Is.True);

            Assert.That(sensor.ObservationCamera, Is.SameAs(actuator.ObservationCamera));
            Assert.That(sensor.ObservationCamera.transform.parent, Is.SameAs(agent.transform));
            Assert.That(
                Quaternion.Angle(
                    sensor.ObservationCamera.transform.localRotation,
                    Quaternion.identity),
                Is.LessThan(0.001f));
            ISensor[] sensors = sensor.CreateSensors();
            Assert.That(sensors, Has.Length.EqualTo(1));
            ObservationSpec observationSpec = sensors[0].GetObservationSpec();
            Assert.That(observationSpec.Shape.Length, Is.EqualTo(3));
            Assert.That(
                observationSpec.Shape[0],
                Is.EqualTo(ResearchBasicContract.ObservationHeight));
            Assert.That(
                observationSpec.Shape[1],
                Is.EqualTo(ResearchBasicContract.ObservationWidth));
            Assert.That(
                observationSpec.Shape[2],
                Is.EqualTo(ResearchBasicContract.ObservationStacks));
            Assert.That(
                sensors[0].GetCompressionSpec().SensorCompressionType,
                Is.EqualTo(SensorCompressionType.None));

            Assert.That(actuator.AgentRoot, Is.SameAs(agent.transform));
            Assert.That(actuator.Target, Is.SameAs(target));
            Assert.That(actuator.TargetLayerMask.value, Is.EqualTo(1 << target.gameObject.layer));
            Assert.That(GameObject.Find("Floor"), Is.Not.Null);
            Assert.That(GameObject.Find("WestWall"), Is.Not.Null);
            Assert.That(GameObject.Find("EastWall"), Is.Not.Null);
            Assert.That(GameObject.Find("NorthWall"), Is.Not.Null);
            Assert.That(GameObject.Find("SouthWall"), Is.Not.Null);
            Light keyLight = GameObject.Find("ResearchBasicKeyLight")?.GetComponent<Light>();
            Assert.That(keyLight, Is.Not.Null);
            Assert.That(keyLight.type, Is.EqualTo(LightType.Directional));
            Assert.That(keyLight.intensity, Is.EqualTo(1.25f).Within(1e-6f));

            Color floorColor = GameObject.Find("Floor")
                .GetComponent<Renderer>().sharedMaterial.color;
            Color wallColor = GameObject.Find("NorthWall")
                .GetComponent<Renderer>().sharedMaterial.color;
            Color targetColor = target.GetComponent<Renderer>().sharedMaterial.color;
            Assert.That(
                GameObject.Find("NorthWall").GetComponent<Renderer>()
                    .sharedMaterial.shader.name,
                Is.EqualTo("Universal Render Pipeline/Lit"));
            Assert.That(
                Rec601Luminance(wallColor),
                Is.GreaterThan(Rec601Luminance(floorColor) + 0.25f));
            Assert.That(
                Rec601Luminance(targetColor),
                Is.GreaterThan(Rec601Luminance(wallColor) + 0.5f));

            foreach (string crosshairName in new[]
                     {
                         "CrosshairLeft",
                         "CrosshairRight",
                         "CrosshairUp",
                         "CrosshairDown"
                     })
            {
                GameObject crosshairPart = GameObject.Find(crosshairName);
                Assert.That(crosshairPart, Is.Not.Null);
                Assert.That(crosshairPart.transform.parent, Is.SameAs(
                    sensor.ObservationCamera.transform));
                Assert.That(crosshairPart.GetComponent<Collider>(), Is.Null);
                Assert.That(
                    crosshairPart.GetComponent<Renderer>().sharedMaterial.shader.name,
                    Is.EqualTo("Universal Render Pipeline/Unlit"));

                bool horizontal = crosshairName == "CrosshairLeft" ||
                                  crosshairName == "CrosshairRight";
                Vector3 scale = crosshairPart.transform.localScale;
                Vector3 position = crosshairPart.transform.localPosition;
                Assert.That(
                    horizontal ? scale.x : scale.y,
                    Is.EqualTo(0.006f).Within(1e-6f));
                Assert.That(
                    horizontal ? scale.y : scale.x,
                    Is.EqualTo(0.001f).Within(1e-6f));
                Assert.That(
                    Mathf.Abs(horizontal ? position.x : position.y),
                    Is.EqualTo(0.006f).Within(1e-6f));
            }

            MonoBehaviour[] components = UnityEngine.Object.FindObjectsByType<MonoBehaviour>(
                FindObjectsInactive.Include,
                FindObjectsSortMode.None);
            string[] typeNames = components
                .Select(component => component.GetType().FullName)
                .ToArray();
            Assert.That(typeNames.Contains("QuickDraw.Core.SimpleFPSController"), Is.False);
            Assert.That(
                typeNames.Any(
                    typeName => typeName != null &&
                                typeName.StartsWith("QuickDraw.AI.", StringComparison.Ordinal)),
                Is.False);
        }

        [Test]
        public void VisualSensorRecoversAPlayModeEntryThatMissedItsFirstReset()
        {
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            ResearchBasicAgent agent =
                UnityEngine.Object.FindFirstObjectByType<ResearchBasicAgent>();
            ResearchBasicVisualSensorComponent sensorComponent =
                agent?.GetComponent<ResearchBasicVisualSensorComponent>();
            Assert.That(agent, Is.Not.Null);
            Assert.That(sensorComponent, Is.Not.Null);

            agent.Initialize();
            ISensor sensor = sensorComponent.CreateSensors()[0];
            Assert.That(sensorComponent.IsStackReady, Is.False);
            Assert.That(agent.Episode.IsActive, Is.False);

            Assert.DoesNotThrow(sensor.Update);

            Assert.That(sensorComponent.IsStackReady, Is.True);
            Assert.That(agent.Episode.IsActive, Is.True);
            Assert.That(agent.NextEpisodeIndex, Is.EqualTo(1));
            (sensor as IDisposable)?.Dispose();
        }

        [Test]
        public void FixedCenterHitscanAgreesWithSlotGeometry()
        {
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            ResearchBasicActuator actuator =
                UnityEngine.Object.FindFirstObjectByType<ResearchBasicActuator>();
            ResearchBasicTarget target =
                UnityEngine.Object.FindFirstObjectByType<ResearchBasicTarget>();
            Assert.That(actuator, Is.Not.Null);
            Assert.That(target, Is.Not.Null);

            target.SetSlot(0);
            actuator.ResetToSlot(0);
            Physics.SyncTransforms();
            ResearchBasicActuationResult aligned = actuator.Apply(
                new ResearchActionTuple(
                    ResearchMovementIntent.Stay,
                    ResearchCombatIntent.Shoot,
                    ResearchUtilityIntent.Idle,
                    0),
                0);
            ResearchBasicActuationResult adjacent = actuator.Apply(
                new ResearchActionTuple(
                    ResearchMovementIntent.Right,
                    ResearchCombatIntent.Shoot,
                    ResearchUtilityIntent.Idle,
                    1),
                1);

            Assert.That(aligned.ShotFired, Is.True);
            Assert.That(aligned.Hit, Is.True);
            Assert.That(adjacent.ShotFired, Is.True);
            Assert.That(adjacent.Hit, Is.False);
        }

        private static float Rec601Luminance(Color color)
        {
            return 0.299f * color.r + 0.587f * color.g + 0.114f * color.b;
        }
    }
}
