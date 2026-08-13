using QuickDraw.AI.Reflex;
using UnityEditor;
using UnityEngine;

namespace QuickDraw.EditorTools
{
    [CustomEditor(typeof(VisibleMotionObserver))]
    public sealed class VisibleMotionObserverEditor : UnityEditor.Editor
    {
        public override void OnInspectorGUI()
        {
            DrawDefaultInspector();

            VisibleMotionObserver observer = (VisibleMotionObserver)target;

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Runtime Visible Motion State", EditorStyles.boldLabel);

            if (!Application.isPlaying)
            {
                EditorGUILayout.HelpBox(
                    "Enter Play Mode to observe measured visible-onset values.",
                    MessageType.Info);
            }

            using (new EditorGUI.DisabledScope(true))
            {
                EditorGUILayout.Toggle(
                    "Awaiting Visible Motion",
                    observer.IsAwaitingVisibleMotion);
                EditorGUILayout.IntField("Visible Motion Count", observer.VisibleMotionCount);
                EditorGUILayout.IntField(
                    "Last Threat Episode ID",
                    observer.LastObservedThreatEpisodeId);
                EditorGUILayout.TextField("Last Signal", observer.LastSignal);
                EditorGUILayout.FloatField(
                    "Confirmed Threat Time (s)",
                    observer.LastConfirmedThreatTime);
                EditorGUILayout.FloatField("Command Time (s)", observer.LastCommandTime);
                EditorGUILayout.FloatField(
                    "Visible Motion Time (s)",
                    observer.LastVisibleMotionTime);
                EditorGUILayout.FloatField(
                    "Position Delta (m)",
                    observer.LastPositionDelta);
                EditorGUILayout.FloatField(
                    "Rotation Delta (deg)",
                    observer.LastRotationDelta);
                EditorGUILayout.FloatField(
                    "Command to Visible (ms)",
                    observer.CommandToVisibleMilliseconds);
                EditorGUILayout.FloatField(
                    "Confirmation to Visible (ms)",
                    observer.ConfirmationToVisibleMilliseconds);
            }
        }

        public override bool RequiresConstantRepaint()
        {
            return Application.isPlaying;
        }
    }
}
