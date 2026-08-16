using System;
using System.Linq;
using NUnit.Framework;
using QuickDraw.Research.Environment;

namespace QuickDraw.Tests.EditMode
{
    public sealed class ResearchSmokeEpisodeAcceptanceTests
    {
        [Test]
        public void SameSeedProducesSameObservationsMasksRewardsAndTerminal()
        {
            var first = new ResearchSmokeEpisode();
            var second = new ResearchSmokeEpisode();
            first.Reset(1, 21001, 4, ResearchSmokeEpisode.TerminalMode);
            second.Reset(1, 21001, 4, ResearchSmokeEpisode.TerminalMode);

            Assert.That(second.Target, Is.EqualTo(first.Target));
            CollectionAssert.AreEqual(
                first.CreateObservation(),
                second.CreateObservation());

            int movementAction = first.Target < 0 ? 1 : first.Target > 0 ? 2 : 0;
            CollectionAssert.AreEqual(
                ReadMask(first),
                ReadMask(second));

            ResearchSmokeStepResult firstMove = first.Step(movementAction, 0);
            ResearchSmokeStepResult secondMove = second.Step(movementAction, 0);
            AssertResultsEqual(firstMove, secondMove);
            CollectionAssert.AreEqual(
                first.CreateObservation(),
                second.CreateObservation());

            ResearchSmokeStepResult firstSubmit = first.Step(0, 1);
            ResearchSmokeStepResult secondSubmit = second.Step(0, 1);
            AssertResultsEqual(firstSubmit, secondSubmit);
            Assert.That(firstSubmit.EndKind, Is.EqualTo(ResearchSmokeEndKind.Terminal));
            Assert.That(firstSubmit.Reason, Is.EqualTo(ResearchSmokeEpisode.GoalReason));
        }

        [Test]
        public void TruncationModeMasksSubmitAndUsesInterruptedDecisionLimitResult()
        {
            var episode = new ResearchSmokeEpisode();
            episode.Reset(2, 21002, 4, ResearchSmokeEpisode.TruncationMode);

            Assert.That(episode.IsActionEnabled(1, 0), Is.True);
            Assert.That(episode.IsActionEnabled(1, 1), Is.False);
            Assert.Throws<ArgumentOutOfRangeException>(() => episode.Step(0, 1));

            ResearchSmokeStepResult result = default;
            for (int index = 0; index < 4; index++)
            {
                result = episode.Step(0, 0);
            }

            Assert.That(result.EndKind, Is.EqualTo(ResearchSmokeEndKind.Truncated));
            Assert.That(result.Reason, Is.EqualTo(ResearchSmokeEpisode.DecisionLimitReason));
            Assert.That(result.Reward, Is.EqualTo(-0.01f));
            Assert.That(episode.StepCount, Is.EqualTo(4));
            Assert.That(episode.IsActive, Is.False);
        }

        [Test]
        public void MechanicalBoundaryMasksPreventOutwardMovement()
        {
            var episode = new ResearchSmokeEpisode();
            episode.Reset(1, 21001, 8, ResearchSmokeEpisode.TerminalMode);

            episode.Step(1, 0);
            Assert.That(episode.Position, Is.EqualTo(-1));
            Assert.That(episode.IsActionEnabled(0, 1), Is.False);
            Assert.That(episode.IsActionEnabled(0, 2), Is.True);
            Assert.Throws<ArgumentOutOfRangeException>(() => episode.Step(1, 0));
        }

        [Test]
        public void ProtocolRejectsUnknownFieldsAndWrongSchema()
        {
            string valid =
                "{\"schema_version\":\"quickdraw.research-side-channel.v1\"," +
                "\"message_type\":\"configure_run\",\"run_id\":\"run-1\"," +
                "\"episode_id\":0,\"sequence\":1,\"payload\":{}}";

            Assert.That(
                ResearchSmokeProtocol.TryDeserialize(
                    valid,
                    out ResearchSmokeEnvelope envelope,
                    out string error),
                Is.True,
                error);
            Assert.That(envelope.MessageType, Is.EqualTo(ResearchSmokeProtocol.ConfigureRun));

            string unknownField = valid.Replace("\"payload\":{}", "\"unknown\":1,\"payload\":{}");
            Assert.That(
                ResearchSmokeProtocol.TryDeserialize(
                    unknownField,
                    out _,
                    out _),
                Is.False);

            string wrongSchema = valid.Replace(
                ResearchSmokeProtocol.SchemaVersion,
                "quickdraw.research-side-channel.v2");
            Assert.That(
                ResearchSmokeProtocol.TryDeserialize(
                    wrongSchema,
                    out _,
                    out _),
                Is.False);
        }

        private static bool[] ReadMask(ResearchSmokeEpisode episode)
        {
            return Enumerable.Range(0, ResearchSmokeEpisode.MovementBranchSize)
                .Select(action => episode.IsActionEnabled(0, action))
                .Concat(
                    Enumerable.Range(0, ResearchSmokeEpisode.SubmitBranchSize)
                        .Select(action => episode.IsActionEnabled(1, action)))
                .ToArray();
        }

        private static void AssertResultsEqual(
            ResearchSmokeStepResult first,
            ResearchSmokeStepResult second)
        {
            Assert.That(second.Reward, Is.EqualTo(first.Reward));
            Assert.That(second.EndKind, Is.EqualTo(first.EndKind));
            Assert.That(second.Reason, Is.EqualTo(first.Reason));
        }
    }
}
