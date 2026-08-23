using System;
using System.IO;
using QuickDraw.Research.Basic;
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
    public static class ResearchBasicBuild
    {
        public const string ScenePath =
            "Assets/_Project/Scenes/Research_Basic.unity";
        private const string OutputArgument = "-quickdrawBasicOutput";
        private const string DefaultOutput =
            "Artifacts/Experiments/r2a-basic/build/QuickDrawResearchBasic.exe";
        private const string MaterialRoot = "Assets/_Project/Settings/ResearchBasic";
        private const int TargetLayer = 8;

        [MenuItem("QuickDraw/Research/Rebuild Basic Scene")]
        public static void RebuildScene()
        {
            Material floorMaterial = CreateOrReplaceMaterial(
                $"{MaterialRoot}Floor.mat",
                new Color(0.045f, 0.06f, 0.08f, 1f),
                true);
            Material wallMaterial = CreateOrReplaceMaterial(
                $"{MaterialRoot}Wall.mat",
                new Color(0.28f, 0.38f, 0.5f, 1f),
                true);
            Material targetMaterial = CreateOrReplaceMaterial(
                $"{MaterialRoot}Target.mat",
                Color.white,
                true);
            Material agentMaterial = CreateOrReplaceMaterial(
                $"{MaterialRoot}Agent.mat",
                new Color(0.16f, 0.2f, 0.24f, 1f),
                true);
            Material crosshairMaterial = CreateOrReplaceMaterial(
                $"{MaterialRoot}Crosshair.mat",
                new Color(0.1f, 0.85f, 0.95f, 1f),
                false);

            Scene scene = EditorSceneManager.NewScene(
                NewSceneSetup.EmptyScene,
                NewSceneMode.Single);

            GameObject environment = new GameObject("ResearchBasicEnvironment");
            GameObject lightObject = new GameObject("ResearchBasicKeyLight");
            lightObject.transform.SetParent(environment.transform, false);
            lightObject.transform.localPosition = new Vector3(0f, 4f, 0f);
            lightObject.transform.localRotation = Quaternion.Euler(50f, -30f, 0f);
            Light keyLight = lightObject.AddComponent<Light>();
            keyLight.type = LightType.Directional;
            keyLight.color = new Color(1f, 0.95686275f, 0.8392157f, 1f);
            keyLight.intensity = 1.25f;
            keyLight.shadows = LightShadows.None;
            RenderSettings.sun = keyLight;

            CreatePrimitive(
                "Floor",
                PrimitiveType.Cube,
                environment.transform,
                new Vector3(0f, -0.25f, 0f),
                new Vector3(8f, 0.5f, 22f),
                floorMaterial);
            CreatePrimitive(
                "WestWall",
                PrimitiveType.Cube,
                environment.transform,
                new Vector3(-4.25f, 1.5f, 0f),
                new Vector3(0.5f, 3.5f, 22f),
                wallMaterial);
            CreatePrimitive(
                "EastWall",
                PrimitiveType.Cube,
                environment.transform,
                new Vector3(4.25f, 1.5f, 0f),
                new Vector3(0.5f, 3.5f, 22f),
                wallMaterial);
            CreatePrimitive(
                "NorthWall",
                PrimitiveType.Cube,
                environment.transform,
                new Vector3(0f, 1.5f, 11.25f),
                new Vector3(9f, 3.5f, 0.5f),
                wallMaterial);
            CreatePrimitive(
                "SouthWall",
                PrimitiveType.Cube,
                environment.transform,
                new Vector3(0f, 1.5f, -11.25f),
                new Vector3(9f, 3.5f, 0.5f),
                wallMaterial);

            GameObject targetObject = CreatePrimitive(
                "ResearchBasicTarget",
                PrimitiveType.Cube,
                environment.transform,
                new Vector3(0f, 1.25f, 8.5f),
                new Vector3(0.5f, 1.5f, 0.5f),
                targetMaterial);
            targetObject.layer = TargetLayer;
            ResearchBasicTarget target =
                targetObject.AddComponent<ResearchBasicTarget>();

            GameObject agentObject = CreatePrimitive(
                "ResearchBasicAgent",
                PrimitiveType.Capsule,
                environment.transform,
                new Vector3(0f, 1f, -8.5f),
                Vector3.one,
                agentMaterial);

            GameObject cameraObject = new GameObject("ObservationCamera");
            cameraObject.transform.SetParent(agentObject.transform, false);
            cameraObject.transform.localPosition = new Vector3(0f, 0.25f, 0f);
            cameraObject.transform.localRotation = Quaternion.identity;
            Camera camera = cameraObject.AddComponent<Camera>();
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(0.01f, 0.01f, 0.015f, 1f);
            camera.fieldOfView = 60f;
            camera.nearClipPlane = 0.05f;
            camera.farClipPlane = 40f;
            camera.depth = -1f;
            camera.enabled = false;
            CreateCrosshairPart(
                "CrosshairLeft",
                cameraObject.transform,
                new Vector3(-0.006f, 0f, 0.11f),
                new Vector3(0.006f, 0.001f, 1f),
                crosshairMaterial);
            CreateCrosshairPart(
                "CrosshairRight",
                cameraObject.transform,
                new Vector3(0.006f, 0f, 0.11f),
                new Vector3(0.006f, 0.001f, 1f),
                crosshairMaterial);
            CreateCrosshairPart(
                "CrosshairUp",
                cameraObject.transform,
                new Vector3(0f, 0.006f, 0.11f),
                new Vector3(0.001f, 0.006f, 1f),
                crosshairMaterial);
            CreateCrosshairPart(
                "CrosshairDown",
                cameraObject.transform,
                new Vector3(0f, -0.006f, 0.11f),
                new Vector3(0.001f, 0.006f, 1f),
                crosshairMaterial);

            BehaviorParameters behavior =
                agentObject.AddComponent<BehaviorParameters>();
            behavior.BehaviorName = ResearchBasicContract.BehaviorName;
            behavior.BehaviorType = BehaviorType.Default;
            behavior.BrainParameters.VectorObservationSize = 0;
            behavior.BrainParameters.NumStackedVectorObservations = 1;
            behavior.BrainParameters.ActionSpec = ActionSpec.MakeDiscrete(
                ResearchBasicContract.MovementBranchSize,
                ResearchBasicContract.CombatBranchSize);
            behavior.UseChildActuators = false;
            behavior.UseChildSensors = true;
            behavior.ObservableAttributeHandling = ObservableAttributeOptions.Ignore;

            ResearchBasicVisualSensorComponent visualSensor =
                agentObject.AddComponent<ResearchBasicVisualSensorComponent>();
            AssignObjectReference(visualSensor, "observationCamera", camera);

            ResearchBasicActuator actuator =
                agentObject.AddComponent<ResearchBasicActuator>();
            AssignObjectReference(actuator, "agentRoot", agentObject.transform);
            AssignObjectReference(actuator, "observationCamera", camera);
            AssignObjectReference(actuator, "target", target);
            AssignInteger(actuator, "targetLayerMask", 1 << TargetLayer);
            AssignFloat(actuator, "hitscanDistance", 40f);

            ResearchBasicAgent agent =
                agentObject.AddComponent<ResearchBasicAgent>();
            agent.MaxStep = 0;
            AssignObjectReference(agent, "actuator", actuator);
            AssignObjectReference(agent, "target", target);
            AssignObjectReference(agent, "visualSensor", visualSensor);
            AssignInteger(
                agent,
                "scenarioSeed",
                ResearchBasicContract.ScenarioSeed);

            DecisionRequester requester =
                agentObject.AddComponent<DecisionRequester>();
            requester.DecisionPeriod =
                ResearchBasicContract.DecisionPeriodFixedSteps;
            requester.DecisionStep = 0;
            requester.TakeActionsBetweenDecisions = true;

            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene, ScenePath))
            {
                throw new InvalidOperationException(
                    $"Could not save the research Basic scene at {ScenePath}.");
            }

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            Debug.Log($"Rebuilt deterministic research Basic scene at {ScenePath}.");
        }

        public static void BuildWindows()
        {
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            string outputPath = GetCommandLineValue(OutputArgument) ?? DefaultOutput;
            string absoluteOutput = Path.GetFullPath(outputPath);
            string outputDirectory = Path.GetDirectoryName(absoluteOutput);
            if (string.IsNullOrEmpty(outputDirectory))
            {
                throw new InvalidOperationException("Basic build output has no directory.");
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
                    $"Research Basic build failed: {report.summary.result} " +
                    $"({report.summary.totalErrors} errors)." );
            }

            Debug.Log(
                $"Research Basic build succeeded at {absoluteOutput} " +
                $"({report.summary.totalSize} bytes)." );
        }

        private static GameObject CreatePrimitive(
            string name,
            PrimitiveType primitiveType,
            Transform parent,
            Vector3 position,
            Vector3 scale,
            Material material)
        {
            GameObject result = GameObject.CreatePrimitive(primitiveType);
            result.name = name;
            result.transform.SetParent(parent, false);
            result.transform.position = position;
            result.transform.localScale = scale;
            result.GetComponent<Renderer>().sharedMaterial = material;
            return result;
        }

        private static Material CreateOrReplaceMaterial(
            string path,
            Color color,
            bool receivesLighting)
        {
            string shaderName = receivesLighting
                ? "Universal Render Pipeline/Lit"
                : "Universal Render Pipeline/Unlit";
            Shader shader = Shader.Find(shaderName);
            if (shader == null)
            {
                throw new InvalidOperationException(
                    $"Required shader is unavailable: {shaderName}.");
            }

            Material material = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (material == null)
            {
                material = new Material(shader);
                AssetDatabase.CreateAsset(material, path);
            }
            else
            {
                material.shader = shader;
            }

            material.color = color;
            if (material.HasProperty("_BaseColor"))
            {
                material.SetColor("_BaseColor", color);
            }

            EditorUtility.SetDirty(material);
            return material;
        }

        private static void CreateCrosshairPart(
            string name,
            Transform parent,
            Vector3 localPosition,
            Vector3 localScale,
            Material material)
        {
            GameObject part = GameObject.CreatePrimitive(PrimitiveType.Quad);
            part.name = name;
            part.transform.SetParent(parent, false);
            part.transform.localPosition = localPosition;
            part.transform.localRotation = Quaternion.identity;
            part.transform.localScale = localScale;
            part.GetComponent<Renderer>().sharedMaterial = material;
            UnityEngine.Object.DestroyImmediate(part.GetComponent<Collider>());
        }

        private static void AssignObjectReference(
            UnityEngine.Object target,
            string propertyName,
            UnityEngine.Object value)
        {
            SerializedObject serializedObject = new SerializedObject(target);
            SerializedProperty property = RequireProperty(
                serializedObject,
                target,
                propertyName);
            property.objectReferenceValue = value;
            serializedObject.ApplyModifiedPropertiesWithoutUndo();
        }

        private static void AssignInteger(
            UnityEngine.Object target,
            string propertyName,
            int value)
        {
            SerializedObject serializedObject = new SerializedObject(target);
            SerializedProperty property = RequireProperty(
                serializedObject,
                target,
                propertyName);
            property.intValue = value;
            serializedObject.ApplyModifiedPropertiesWithoutUndo();
        }

        private static void AssignFloat(
            UnityEngine.Object target,
            string propertyName,
            float value)
        {
            SerializedObject serializedObject = new SerializedObject(target);
            SerializedProperty property = RequireProperty(
                serializedObject,
                target,
                propertyName);
            property.floatValue = value;
            serializedObject.ApplyModifiedPropertiesWithoutUndo();
        }

        private static SerializedProperty RequireProperty(
            SerializedObject serializedObject,
            UnityEngine.Object target,
            string propertyName)
        {
            SerializedProperty property = serializedObject.FindProperty(propertyName);
            if (property == null)
            {
                throw new MissingFieldException(target.GetType().FullName, propertyName);
            }

            return property;
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
