using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;

namespace QuickDraw.Logging
{
    public class JsonlLogger : MonoBehaviour
    {
        public static JsonlLogger Instance { get; private set; }

        private readonly List<string> _buffer = new List<string>(1024);
        private string _path;

        void Awake()
        {
            if (Instance != null) { Destroy(gameObject); return; }
            Instance = this;
            DontDestroyOnLoad(gameObject);

            var date = System.DateTime.Now;
            var fname = $"{date:yyyyMMdd}_session.jsonl";
            _path = Path.Combine(Application.persistentDataPath, fname);

            Log(new { t = "session_start", ts = Time.realtimeSinceStartup, unity = Application.unityVersion });
        }

        public void Log(object o)
        {
            // Serialize with Unity's JsonUtility (limited) or a lightweight custom method.
            // Keep it simple: build a basic JSON payload manually where needed.
            var line = MiniJson.ToJson(o);
            lock (_buffer) _buffer.Add(line);
        }

        void OnApplicationQuit()
        {
            // Example summary: compute simple latency stats if collected
            try
            {
                File.AppendAllLines(_path, _buffer, Encoding.UTF8);
            }
            catch (System.Exception e)
            {
                Debug.LogWarning($"JsonlLogger write failed: {e.Message}");
            }
        }
    }

    // Minimal JSON helper (stringly-typed fallback). Replace with Newtonsoft if desired.
    internal static class MiniJson
    {
        public static string ToJson(object o)
        {
            // For this scaffold, delegate to JsonUtility; it's fine for simple anonymous objects.
            return JsonUtility.ToJson(o);
        }
    }
}
