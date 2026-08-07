using QuickDraw.AI.Behavior;
using UnityEditor;
using UnityEngine;

namespace QuickDraw.EditorTools
{
    [CustomEditor(typeof(NpcBehaviorController))]
    public sealed class NpcBehaviorControllerEditor : UnityEditor.Editor
    {
        public override void OnInspectorGUI()
        {
            DrawDefaultInspector();

            NpcBehaviorController controller = (NpcBehaviorController)target;

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Runtime Interruption State", EditorStyles.boldLabel);

            if (!Application.isPlaying)
            {
                EditorGUILayout.HelpBox(
                    "Enter Play Mode to observe runtime interruption values.",
                    MessageType.Info);
            }

            using (new EditorGUI.DisabledScope(true))
            {
                EditorGUILayout.IntField("Interruption Count", controller.InterruptionCount);
                EditorGUILayout.IntField(
                    "Last Threat Episode ID",
                    controller.LastHandledThreatEpisodeId);
                EditorGUILayout.TextField(
                    "Interrupted Activity",
                    controller.InterruptedActivityName);
                EditorGUILayout.TextField(
                    "Interruption Reason",
                    controller.InterruptionReason);
                EditorGUILayout.FloatField(
                    "Interruption Time (s)",
                    controller.InterruptionTime);
                EditorGUILayout.EnumPopup(
                    "Interruption Outcome",
                    controller.InterruptionOutcome);
            }
        }

        public override bool RequiresConstantRepaint()
        {
            return Application.isPlaying;
        }
    }
}
