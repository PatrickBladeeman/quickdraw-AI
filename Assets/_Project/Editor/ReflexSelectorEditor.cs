using QuickDraw.AI.Reflex;
using UnityEditor;
using UnityEngine;

namespace QuickDraw.EditorTools
{
    [CustomEditor(typeof(ReflexSelector))]
    public sealed class ReflexSelectorEditor : UnityEditor.Editor
    {
        public override void OnInspectorGUI()
        {
            DrawDefaultInspector();

            ReflexSelector selector = (ReflexSelector)target;

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Runtime Reflex State", EditorStyles.boldLabel);

            if (!Application.isPlaying)
            {
                EditorGUILayout.HelpBox(
                    "Enter Play Mode to observe runtime reflex values.",
                    MessageType.Info);
            }

            using (new EditorGUI.DisabledScope(true))
            {
                EditorGUILayout.IntField("Command Count", selector.CommandCount);
                EditorGUILayout.IntField(
                    "Last Threat Episode ID",
                    selector.LastCommandedThreatEpisodeId);
                EditorGUILayout.TextField(
                    "Last Variant",
                    selector.LastCommandedVariant);
                EditorGUILayout.FloatField(
                    "Confirmed Threat Time (s)",
                    selector.LastConfirmedThreatTime);
                EditorGUILayout.FloatField(
                    "Command Time (s)",
                    selector.LastCommandTime);
                EditorGUILayout.FloatField(
                    "Requested Step (m)",
                    selector.LastRequestedStepDistance);
                EditorGUILayout.FloatField(
                    "Applied Step (m)",
                    selector.LastAppliedStepDistance);
                EditorGUILayout.FloatField(
                    "Yaw Offset (deg)",
                    selector.LastYawOffset);
                EditorGUILayout.EnumFlagsField(
                    "Collision Flags",
                    selector.LastCollisionFlags);
                EditorGUILayout.Vector3Field(
                    "Command Start Position",
                    selector.LastCommandStartPosition);
                EditorGUILayout.Vector3Field(
                    "Command Start Rotation",
                    selector.LastCommandStartRotation.eulerAngles);
            }
        }

        public override bool RequiresConstantRepaint()
        {
            return Application.isPlaying;
        }
    }
}
