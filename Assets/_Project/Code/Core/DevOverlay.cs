using UnityEngine;

namespace QuickDraw.Core
{
    public class DevOverlay : MonoBehaviour
    {
        float _delta;
        float _fps;
        GUIStyle _style;

        void Awake()
        {
            _style = new GUIStyle
            {
                fontSize = 14,
                normal = { textColor = Color.white }
            };
        }

        void Update()
        {
            _delta += (Time.unscaledDeltaTime - _delta) * 0.1f;
            _fps = 1.0f / Mathf.Max(0.0001f, _delta);
        }

        void OnGUI()
        {
            GUILayout.BeginArea(new Rect(8, 8, 360, 200));
            GUILayout.Label($"FPS: {_fps:0.0}", _style);
            GUILayout.Label($"Realtime: {Time.realtimeSinceStartup:0.000}s", _style);
            GUILayout.EndArea();
        }
    }
}
