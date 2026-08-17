using System;
using NUnit.Framework;
using QuickDraw.Research.Basic;
using UnityEngine;

namespace QuickDraw.Tests.EditMode
{
    public sealed class ResearchBasicVisualAcceptanceTests
    {
        [Test]
        public void ResetCopiesOnePostResetFrameIntoEveryStackSlot()
        {
            var stack = new ResearchBasicFrameStack(2, 2, 4);
            float[] resetFrame = { 0.1f, 0.2f, 0.3f, 0.4f };

            stack.ResetWithFrame(resetFrame);

            for (int frame = 0; frame < 4; frame++)
            {
                Assert.That(stack.GetValue(frame, 0, 0), Is.EqualTo(0.1f));
                Assert.That(stack.GetValue(frame, 0, 1), Is.EqualTo(0.2f));
                Assert.That(stack.GetValue(frame, 1, 0), Is.EqualTo(0.3f));
                Assert.That(stack.GetValue(frame, 1, 1), Is.EqualTo(0.4f));
            }
        }

        [Test]
        public void PushOrderIsOldestToNewest()
        {
            var stack = new ResearchBasicFrameStack(1, 1, 4);
            stack.ResetWithFrame(new[] { 1f });
            stack.PushFrame(new[] { 2f });
            stack.PushFrame(new[] { 3f });
            stack.PushFrame(new[] { 4f });
            stack.PushFrame(new[] { 5f });

            CollectionAssert.AreEqual(
                new[] { 2f, 3f, 4f, 5f },
                new[]
                {
                    stack.GetValue(0, 0, 0),
                    stack.GetValue(1, 0, 0),
                    stack.GetValue(2, 0, 0),
                    stack.GetValue(3, 0, 0)
                });
        }

        [Test]
        public void StaleFrameStackFailsClosed()
        {
            var stack = new ResearchBasicFrameStack(1, 1, 4);

            Assert.Throws<InvalidOperationException>(
                () => stack.GetValue(0, 0, 0));
            Assert.Throws<InvalidOperationException>(
                () => stack.PushFrame(new[] { 1f }));

            stack.ResetWithFrame(new[] { 1f });
            stack.Invalidate();

            Assert.That(stack.IsReady, Is.False);
            Assert.Throws<InvalidOperationException>(
                () => stack.GetValue(0, 0, 0));
        }

        [Test]
        public void FrameShapeIsStrict()
        {
            var stack = new ResearchBasicFrameStack(2, 2, 4);
            Assert.Throws<ArgumentException>(
                () => stack.ResetWithFrame(new float[3]));
        }

        [TestCase(255, 0, 0, 0.299f)]
        [TestCase(0, 255, 0, 0.587f)]
        [TestCase(0, 0, 255, 0.114f)]
        [TestCase(255, 255, 255, 1f)]
        [TestCase(0, 0, 0, 0f)]
        public void GrayscaleEncodingIsRec601(
            byte red,
            byte green,
            byte blue,
            float expected)
        {
            float actual = ResearchBasicVisualEncoding.ToRec601Grayscale(
                new Color32(red, green, blue, 255));
            Assert.That(actual, Is.EqualTo(expected).Within(1e-6f));
        }
    }
}
