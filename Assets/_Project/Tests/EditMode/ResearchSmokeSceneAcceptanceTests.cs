using System;
using System.IO;
using System.Linq;
using NUnit.Framework;
using QuickDraw.Research.Environment;
using Unity.MLAgents;
using Unity.MLAgents.Policies;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace QuickDraw.Tests.EditMode
{
    public sealed class ResearchSmokeSceneAcceptanceTests
    {
        private const string ScenePath =
            "Assets/_Project/Scenes/Research_Smoke.unity";

        [Test]
        public void PackageAndDedicatedSceneMatchTheSmokeBoundary()
        {
            string manifestPath = Path.GetFullPath("Packages/manifest.json");
            string packageLockPath = Path.GetFullPath("Packages/packages-lock.json");
            StringAssert.Contains(
                "\"com.unity.ml-agents\": \"4.0.0\"",
                File.ReadAllText(manifestPath));
            StringAssert.Contains(
                "\"com.unity.ml-agents\"",
                File.ReadAllText(packageLockPath));

            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            ResearchSmokeCoordinator coordinator =
                UnityEngine.Object.FindFirstObjectByType<ResearchSmokeCoordinator>();
            ResearchSmokeAgent agent =
                UnityEngine.Object.FindFirstObjectByType<ResearchSmokeAgent>();
            BehaviorParameters behavior = agent?.GetComponent<BehaviorParameters>();
            DecisionRequester requester = agent?.GetComponent<DecisionRequester>();

            Assert.That(coordinator, Is.Not.Null);
            Assert.That(agent, Is.Not.Null);
            Assert.That(behavior, Is.Not.Null);
            Assert.That(requester, Is.Not.Null);
            Assert.That(coordinator.Agent, Is.SameAs(agent));
            Assert.That(agent.Coordinator, Is.SameAs(coordinator));
            Assert.That(agent.MaxStep, Is.Zero);
            Assert.That(behavior.BehaviorName, Is.EqualTo(ResearchSmokeProtocol.BehaviorName));
            Assert.That(behavior.BehaviorType, Is.EqualTo(BehaviorType.Default));
            Assert.That(
                behavior.BrainParameters.VectorObservationSize,
                Is.EqualTo(ResearchSmokeEpisode.ObservationSize));
            CollectionAssert.AreEqual(
                new[]
                {
                    ResearchSmokeEpisode.MovementBranchSize,
                    ResearchSmokeEpisode.SubmitBranchSize
                },
                behavior.BrainParameters.ActionSpec.BranchSizes);
            Assert.That(requester.DecisionPeriod, Is.EqualTo(1));
            Assert.That(requester.DecisionStep, Is.Zero);
            Assert.That(requester.TakeActionsBetweenDecisions, Is.True);

            MonoBehaviour[] components = UnityEngine.Object.FindObjectsByType<MonoBehaviour>(
                FindObjectsInactive.Include,
                FindObjectsSortMode.None);
            string[] typeNames = components
                .Select(component => component.GetType().FullName)
                .ToArray();
            Assert.That(
                typeNames.Contains("QuickDraw.Core.SimpleFPSController"),
                Is.False);
            Assert.That(
                typeNames.Any(
                    typeName => typeName != null &&
                                typeName.StartsWith(
                                    "QuickDraw.AI.",
                                    StringComparison.Ordinal)),
                Is.False);
        }
    }
}
