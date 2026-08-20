using System;
using Unity.MLAgents.Sensors;
using UnityEngine;

namespace QuickDraw.Research.Basic
{
    public static class ResearchBasicVisualEncoding
    {
        public static float ToRec601Grayscale(Color32 pixel)
        {
            return (0.299f * pixel.r +
                    0.587f * pixel.g +
                    0.114f * pixel.b) / 255f;
        }
    }

    public sealed class ResearchBasicFrameStack
    {
        private readonly int _frameSize;
        private readonly float[][] _frames;
        private int _latestIndex;

        public ResearchBasicFrameStack(int width, int height, int stackCount)
        {
            if (width <= 0 || height <= 0 || stackCount <= 0)
            {
                throw new ArgumentOutOfRangeException(
                    nameof(width),
                    "Frame-stack dimensions must be positive.");
            }

            Width = width;
            Height = height;
            StackCount = stackCount;
            _frameSize = width * height;
            _frames = new float[stackCount][];
            for (int index = 0; index < stackCount; index++)
            {
                _frames[index] = new float[_frameSize];
            }
        }

        public int Width { get; }
        public int Height { get; }
        public int StackCount { get; }
        public bool IsReady { get; private set; }

        public void ResetWithFrame(float[] frame)
        {
            ValidateFrame(frame);
            for (int index = 0; index < StackCount; index++)
            {
                Array.Copy(frame, _frames[index], _frameSize);
            }

            _latestIndex = StackCount - 1;
            IsReady = true;
        }

        public void PushFrame(float[] frame)
        {
            if (!IsReady)
            {
                throw new InvalidOperationException(
                    "The frame stack must be reset from a post-reset frame first.");
            }

            ValidateFrame(frame);
            _latestIndex = (_latestIndex + 1) % StackCount;
            Array.Copy(frame, _frames[_latestIndex], _frameSize);
        }

        public float GetValue(int logicalIndex, int y, int x)
        {
            if (!IsReady)
            {
                throw new InvalidOperationException("The frame stack is stale or uninitialized.");
            }

            if (logicalIndex < 0 || logicalIndex >= StackCount)
            {
                throw new ArgumentOutOfRangeException(nameof(logicalIndex));
            }

            if (y < 0 || y >= Height || x < 0 || x >= Width)
            {
                throw new ArgumentOutOfRangeException(nameof(y));
            }

            int frameIndex =
                (_latestIndex + 1 + logicalIndex) % StackCount;
            return _frames[frameIndex][y * Width + x];
        }

        public void CopyLatestFrame(float[] destination)
        {
            if (!IsReady)
            {
                throw new InvalidOperationException("The frame stack is stale or uninitialized.");
            }

            ValidateFrame(destination);
            Array.Copy(_frames[_latestIndex], destination, _frameSize);
        }

        public void Invalidate()
        {
            for (int index = 0; index < StackCount; index++)
            {
                Array.Clear(_frames[index], 0, _frameSize);
            }

            _latestIndex = 0;
            IsReady = false;
        }

        private void ValidateFrame(float[] frame)
        {
            if (frame == null || frame.Length != _frameSize)
            {
                throw new ArgumentException(
                    $"Frame length must be exactly {_frameSize}.",
                    nameof(frame));
            }
        }
    }

    [DisallowMultipleComponent]
    public sealed class ResearchBasicVisualSensorComponent : SensorComponent
    {
        [SerializeField] private Camera observationCamera;
        [SerializeField] private string sensorName = "ResearchBasicVisual";

        private ResearchBasicVisualSensor _sensor;

        public Camera ObservationCamera => observationCamera;
        public string SensorName => sensorName;
        public bool IsStackReady => _sensor != null && _sensor.IsStackReady;

        public override ISensor[] CreateSensors()
        {
            if (observationCamera == null)
            {
                throw new InvalidOperationException(
                    "ResearchBasicVisualSensorComponent requires a camera.");
            }

            ResearchBasicAgent agent = GetComponent<ResearchBasicAgent>();
            if (agent == null)
            {
                throw new InvalidOperationException(
                    "ResearchBasicVisualSensorComponent requires a ResearchBasicAgent.");
            }

            DisposeSensor();
            _sensor = new ResearchBasicVisualSensor(
                observationCamera,
                sensorName,
                agent.RecoverFromMissingVisualSensorReset);
            return new ISensor[] { _sensor };
        }

        public void PrimeStackFromCurrentFrame()
        {
            if (_sensor == null)
            {
                throw new InvalidOperationException(
                    "The visual sensor has not been created by the Agent.");
            }

            _sensor.PrimeStackFromCurrentFrame();
        }

        private void OnDestroy()
        {
            DisposeSensor();
        }

        private void DisposeSensor()
        {
            _sensor?.Dispose();
            _sensor = null;
        }
    }

    internal sealed class ResearchBasicVisualSensor : ISensor, IDisposable
    {
        private readonly Camera _camera;
        private readonly string _name;
        private readonly Texture2D _texture;
        private readonly float[] _capture;
        private readonly ResearchBasicFrameStack _stack;
        private readonly Action _recoverFromMissingReset;

        public ResearchBasicVisualSensor(
            Camera camera,
            string name,
            Action recoverFromMissingReset)
        {
            _camera = camera != null
                ? camera
                : throw new ArgumentNullException(nameof(camera));
            _name = string.IsNullOrWhiteSpace(name)
                ? throw new ArgumentException("Sensor name is required.", nameof(name))
                : name;
            _recoverFromMissingReset = recoverFromMissingReset ??
                throw new ArgumentNullException(nameof(recoverFromMissingReset));
            _texture = new Texture2D(
                ResearchBasicContract.ObservationWidth,
                ResearchBasicContract.ObservationHeight,
                TextureFormat.RGB24,
                false);
            _capture = new float[
                ResearchBasicContract.ObservationWidth *
                ResearchBasicContract.ObservationHeight];
            _stack = new ResearchBasicFrameStack(
                ResearchBasicContract.ObservationWidth,
                ResearchBasicContract.ObservationHeight,
                ResearchBasicContract.ObservationStacks);
        }

        public bool IsStackReady => _stack.IsReady;

        public ObservationSpec GetObservationSpec()
        {
            return new ObservationSpec(
                new Unity.MLAgents.InplaceArray<int>(
                    ResearchBasicContract.ObservationHeight,
                    ResearchBasicContract.ObservationWidth,
                    ResearchBasicContract.ObservationStacks),
                new Unity.MLAgents.InplaceArray<DimensionProperty>(
                    DimensionProperty.TranslationalEquivariance,
                    DimensionProperty.TranslationalEquivariance,
                    DimensionProperty.None));
        }

        public int Write(ObservationWriter writer)
        {
            if (!_stack.IsReady)
            {
                throw new InvalidOperationException(
                    "The visual stack was not primed after episode reset.");
            }

            int writeIndex = 0;
            for (int y = 0;
                 y < ResearchBasicContract.ObservationHeight;
                 y++)
            {
                for (int x = 0;
                     x < ResearchBasicContract.ObservationWidth;
                     x++)
                {
                    for (int frame = 0;
                         frame < ResearchBasicContract.ObservationStacks;
                         frame++)
                    {
                        writer[writeIndex] = _stack.GetValue(frame, y, x);
                        writeIndex++;
                    }
                }
            }

            return ResearchBasicContract.ObservationWidth *
                   ResearchBasicContract.ObservationHeight *
                   ResearchBasicContract.ObservationStacks;
        }

        public byte[] GetCompressedObservation()
        {
            return Array.Empty<byte>();
        }

        public void Update()
        {
            CaptureCurrentFrame();
            if (_stack.IsReady)
            {
                _stack.PushFrame(_capture);
                return;
            }

            _recoverFromMissingReset();
            CaptureCurrentFrame();
            _stack.ResetWithFrame(_capture);
        }

        public void Reset()
        {
            _stack.Invalidate();
        }

        public CompressionSpec GetCompressionSpec()
        {
            return CompressionSpec.Default();
        }

        public string GetName()
        {
            return _name;
        }

        public void PrimeStackFromCurrentFrame()
        {
            CaptureCurrentFrame();
            _stack.ResetWithFrame(_capture);
        }

        public void Dispose()
        {
            if (_texture == null)
            {
                return;
            }

            if (Application.isPlaying)
            {
                UnityEngine.Object.Destroy(_texture);
            }
            else
            {
                UnityEngine.Object.DestroyImmediate(_texture);
            }
        }

        private void CaptureCurrentFrame()
        {
            CameraSensor.ObservationToTexture(
                _camera,
                _texture,
                ResearchBasicContract.ObservationWidth,
                ResearchBasicContract.ObservationHeight);
            Color32[] pixels = _texture.GetPixels32();
            int width = ResearchBasicContract.ObservationWidth;
            int height = ResearchBasicContract.ObservationHeight;
            for (int y = 0; y < height; y++)
            {
                int sourceY = height - 1 - y;
                for (int x = 0; x < width; x++)
                {
                    Color32 pixel = pixels[sourceY * width + x];
                    _capture[y * width + x] =
                        ResearchBasicVisualEncoding.ToRec601Grayscale(pixel);
                }
            }
        }
    }
}
