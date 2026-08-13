using QuickDraw.Logging;
using UnityEditor;
using UnityEngine;

namespace QuickDraw.EditorTools
{
    [CustomEditor(typeof(JsonlLogger))]
    public sealed class JsonlLoggerEditor : UnityEditor.Editor
    {
        public override void OnInspectorGUI()
        {
            DrawDefaultInspector();

            JsonlLogger logger = (JsonlLogger)target;

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Runtime Telemetry State", EditorStyles.boldLabel);

            if (!Application.isPlaying)
            {
                EditorGUILayout.HelpBox(
                    "Enter Play Mode to inspect the active telemetry session.",
                    MessageType.Info);
            }

            using (new EditorGUI.DisabledScope(true))
            {
                EditorGUILayout.TextField("Session ID", logger.SessionId);
                EditorGUILayout.TextField("Log Path", logger.CurrentLogPath);
                EditorGUILayout.IntField("Pending Events", logger.PendingCount);
                EditorGUILayout.IntField("Buffered Lines", logger.BufferedLineCount);
                EditorGUILayout.IntField("Queued Events", logger.QueuedEventCount);
                EditorGUILayout.IntField("Serialized Events", logger.SerializedEventCount);
                EditorGUILayout.IntField("Written Lines", logger.WrittenLineCount);
                EditorGUILayout.IntField("Dropped Events", logger.DroppedEventCount);
                EditorGUILayout.IntField("Failed Flushes", logger.FailedFlushCount);
                EditorGUILayout.TextField("Last Error", logger.LastError);
            }
        }

        public override bool RequiresConstantRepaint()
        {
            return Application.isPlaying;
        }
    }
}
