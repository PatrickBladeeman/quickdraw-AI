using System;
using System.IO;
using QuickDraw.Research.Environment;
using Unity.MLAgents;
using Unity.MLAgents.Actuators;
using Unity.MLAgents.Policies;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace QuickDraw.Editor
{
    public static class ResearchSmokeBuild
    {
        public const string ScenePath = "Assets/_Project/Scenes/Research_Smoke.unity";
        private const string OutputArgument = "-quickdrawSmokeOutput";
        private const string DefaultOutput =
            "Artifacts/Experiments/r1b-smoke/build/QuickDrawResearchSmoke.exe";

        [MenuItem("QuickDraw/Research/Rebuild Communicator Smoke Scene")]
        public static void RebuildScene()
        {
            Scene scene = EditorSceneManager.NewScene(
                NewSceneSetup.EmptyScene,
                NewSceneMode.Single);

            GameObject coordinatorObject = new GameObject("ResearchSmokeCoordinator");
            ResearchSmokeCoordinator coordinator =
                coordinatorObject.AddComponent<ResearchSmokeCoordinator>();

            GameObject agentObject = new GameObject("ResearchSmokeAgent");
            BehaviorParameters behavior = agentObject.AddComponent<BehaviorParameters>();
            behavior.BehaviorName = ResearchSmokeProtocol.BehaviorName;
            behavior.BehaviorType = BehaviorType.Default;
            behavior.BrainParameters.VectorObservationSize =
                ResearchSmokeEpisode.ObservationSize;
            behavior.BrainParameters.NumStackedVectorObservations = 1;
            behavior.BrainParameters.ActionSpec = ActionSpec.MakeDiscrete(
                ResearchSmokeEpisode.MovementBranchSize,
                ResearchSmokeEpisode.SubmitBranchSize);
            behavior.UseChildActuators = false;
            behavior.UseChildSensors = false;
            behavior.ObservableAttributeHandling = ObservableAttributeOptions.Ignore;

            ResearchSmokeAgent agent = agentObject.AddComponent<ResearchSmokeAgent>();
            agent.MaxStep = 0;
            DecisionRequester requester = agentObject.AddComponent<DecisionRequester>();
            requester.DecisionPeriod = 1;
            requester.DecisionStep = 0;
            requester.TakeActionsBetweenDecisions = true;

            AssignObjectReference(coordinator, "agent", agent);
            AssignObjectReference(agent, "coordinator", coordinator);

            GameObject cameraObject = new GameObject("SmokeCamera");
            Camera camera = cameraObject.AddComponent<Camera>();
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = Color.black;
            camera.orthographic = true;
            cameraObject.transform.position = new Vector3(0f, 0f, -10f);

            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene, ScenePath))
            {
                throw new InvalidOperationException(
                    $"Could not save the research smoke scene at {ScenePath}.");
            }

            AssetDatabase.SaveAssets();
            Debug.Log($"Rebuilt deterministic research smoke scene at {ScenePath}.");
        }

        public static void BuildWindows()
        {
            if (!File.Exists(ScenePath))
            {
                RebuildScene();
            }

            string outputPath = GetCommandLineValue(OutputArgument) ?? DefaultOutput;
            string absoluteOutput = Path.GetFullPath(outputPath);
            string outputDirectory = Path.GetDirectoryName(absoluteOutput);
            if (string.IsNullOrEmpty(outputDirectory))
            {
                throw new InvalidOperationException("Smoke build output has no directory.");
            }

            Directory.CreateDirectory(outputDirectory);
            BuildReport report = BuildPipeline.BuildPlayer(
                new BuildPlayerOptions
                {
                    scenes = new[] { ScenePath },
                    locationPathName = absoluteOutput,
                    target = BuildTarget.StandaloneWindows64,
                    options = BuildOptions.None
                });

            if (report.summary.result != BuildResult.Succeeded)
            {
                throw new InvalidOperationException(
                    $"Research smoke build failed: {report.summary.result} " +
                    $"({report.summary.totalErrors} errors).");
            }

            Debug.Log(
                $"Research smoke build succeeded at {absoluteOutput} " +
                $"({report.summary.totalSize} bytes).");
        }

        private static void AssignObjectReference(
            UnityEngine.Object target,
            string propertyName,
            UnityEngine.Object value)
        {
            var serializedObject = new SerializedObject(target);
            SerializedProperty property = serializedObject.FindProperty(propertyName);
            if (property == null)
            {
                throw new MissingFieldException(target.GetType().FullName, propertyName);
            }

            property.objectReferenceValue = value;
            serializedObject.ApplyModifiedPropertiesWithoutUndo();
        }

        private static string GetCommandLineValue(string argumentName)
        {
            string[] arguments = Environment.GetCommandLineArgs();
            for (int index = 0; index < arguments.Length - 1; index++)
            {
                if (string.Equals(
                        arguments[index],
                        argumentName,
                        StringComparison.Ordinal))
                {
                    return arguments[index + 1];
                }
            }

            return null;
        }
    }
}
