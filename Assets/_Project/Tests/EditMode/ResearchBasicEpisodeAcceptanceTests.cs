using System;
using System.Linq;
using NUnit.Framework;
using QuickDraw.Research.Actuation;
using QuickDraw.Research.Basic;

namespace QuickDraw.Tests.EditMode
{
    public sealed class ResearchBasicEpisodeAcceptanceTests
    {
        [Test]
        public void FixedScenarioSeedProducesARepeatableTargetSequence()
        {
            int[] first = Enumerable.Range(0, 12)
                .Select(index => ResearchBasicEpisode.SampleTargetSlot(
                    ResearchBasicContract.ScenarioSeed,
                    index))
                .ToArray();
            int[] second = Enumerable.Range(0, 12)
                .Select(index => ResearchBasicEpisode.SampleTargetSlot(
                    ResearchBasicContract.ScenarioSeed,
                    index))
                .ToArray();

            CollectionAssert.AreEqual(first, second);
            CollectionAssert.AreEqual(
                new[] { 2, -4, -2, -4, -2, 1, 0, 0, 2, 2, -2, -4 },
                first);
            Assert.That(
                first.All(
                    slot => slot >= ResearchBasicContract.MinimumSlot &&
                            slot <= ResearchBasicContract.MaximumSlot),
                Is.True);
            Assert.That(first.Distinct().Count(), Is.GreaterThan(1));
        }

        [Test]
        public void AllSixJointActionsHaveTheRegisteredMechanicsAndReward()
        {
            for (int movementBranch = 0;
                 movementBranch < ResearchBasicContract.MovementBranchSize;
                 movementBranch++)
            {
                for (int combatBranch = 0;
                     combatBranch < ResearchBasicContract.CombatBranchSize;
                     combatBranch++)
                {
                    var episode = new ResearchBasicEpisode();
                    episode.Reset(
                        ResearchBasicContract.ScenarioSeed,
                        movementBranch * ResearchBasicContract.CombatBranchSize +
                        combatBranch);
                    ResearchActionTuple action = ResearchBasicContract.MapAction(
                        movementBranch,
                        combatBranch,
                        0);
                    int expectedPosition = movementBranch switch
                    {
                        1 => -1,
                        2 => 1,
                        _ => 0
                    };
                    bool expectedShot = combatBranch == 1;
                    bool expectedHit =
                        expectedShot && expectedPosition == episode.TargetSlot;

                    ResearchBasicStepResult result = episode.Step(
                        action,
                        expectedHit);
                    float expectedReward = ResearchBasicContract.PerDecisionReward;
                    if (expectedShot)
                    {
                        expectedReward += expectedHit
                            ? ResearchBasicContract.HitReward
                            : ResearchBasicContract.MissReward;
                    }

                    Assert.That(result.PositionSlot, Is.EqualTo(expectedPosition));
                    Assert.That(result.ShotFired, Is.EqualTo(expectedShot));
                    Assert.That(result.Hit, Is.EqualTo(expectedHit));
                    Assert.That(result.Reward, Is.EqualTo(expectedReward).Within(1e-6f));
                    Assert.That(episode.ShotsFired, Is.EqualTo(expectedShot ? 1 : 0));
                    Assert.That(episode.Misses, Is.EqualTo(
                        expectedShot && !expectedHit ? 1 : 0));
                    Assert.That(
                        episode.RemainingAmmunition,
                        Is.EqualTo(
                            ResearchBasicContract.AmmunitionCapacity -
                            (expectedShot ? 1 : 0)));
                }
            }
        }

        [Test]
        public void HitIsTerminalAndCannotContinue()
        {
            var episode = new ResearchBasicEpisode();
            int episodeIndex = FindEpisodeIndexForTargetSlot(0);
            episode.Reset(ResearchBasicContract.ScenarioSeed, episodeIndex);
            ResearchActionTuple shoot = ResearchBasicContract.MapAction(0, 1, 0);

            ResearchBasicStepResult result = episode.Step(shoot, true);

            Assert.That(result.EndKind, Is.EqualTo(ResearchBasicEndKind.Terminal));
            Assert.That(result.Reason, Is.EqualTo(ResearchBasicContract.TargetHitReason));
            Assert.That(result.Reward, Is.EqualTo(0.99f).Within(1e-6f));
            Assert.That(episode.IsActive, Is.False);
            Assert.Throws<InvalidOperationException>(() => episode.Step(shoot, true));
        }

        [Test]
        public void ThreeHundredthDecisionIsAnInterruptedLimitOutcome()
        {
            var episode = new ResearchBasicEpisode();
            episode.Reset(ResearchBasicContract.ScenarioSeed, 0);
            ResearchBasicStepResult result = default;

            for (int decision = 0;
                 decision < ResearchBasicContract.DecisionLimit;
                 decision++)
            {
                result = episode.Step(
                    ResearchBasicContract.MapAction(0, 0, decision),
                    false);
            }

            Assert.That(result.EndKind, Is.EqualTo(ResearchBasicEndKind.Truncated));
            Assert.That(
                result.Reason,
                Is.EqualTo(ResearchBasicContract.DecisionLimitReason));
            Assert.That(result.DecisionCount, Is.EqualTo(300));
            Assert.That(result.CumulativeReward, Is.EqualTo(-3f).Within(1e-5f));
            Assert.That(episode.IsActive, Is.False);
        }

        [Test]
        public void ResetRestoresEveryBasicEpisodeStateField()
        {
            var episode = new ResearchBasicEpisode();
            episode.Reset(ResearchBasicContract.ScenarioSeed, 0);
            episode.Step(ResearchBasicContract.MapAction(2, 1, 0), false);

            episode.Reset(ResearchBasicContract.ScenarioSeed, 0);

            Assert.That(episode.PositionSlot, Is.Zero);
            Assert.That(episode.DecisionCount, Is.Zero);
            Assert.That(episode.ShotsFired, Is.Zero);
            Assert.That(episode.Misses, Is.Zero);
            Assert.That(episode.CumulativeReward, Is.Zero);
            Assert.That(
                episode.RemainingAmmunition,
                Is.EqualTo(ResearchBasicContract.AmmunitionCapacity));
            Assert.That(episode.CooldownDecisionsRemaining, Is.Zero);
            Assert.That(
                episode.TargetSlot,
                Is.EqualTo(ResearchBasicEpisode.SampleTargetSlot(
                    ResearchBasicContract.ScenarioSeed,
                    0)));
            Assert.That(episode.IsActive, Is.True);
        }

        [Test]
        public void BoundaryMasksOnlyMechanicallyImpossibleMovement()
        {
            var episode = new ResearchBasicEpisode();
            episode.Reset(ResearchBasicContract.ScenarioSeed, 0);
            for (int decision = 0;
                 decision < -ResearchBasicContract.MinimumSlot;
                 decision++)
            {
                episode.Step(
                    ResearchBasicContract.MapAction(1, 0, decision),
                    false);
            }

            Assert.That(episode.PositionSlot, Is.EqualTo(-4));
            Assert.That(episode.IsActionEnabled(0, 0), Is.True);
            Assert.That(episode.IsActionEnabled(0, 1), Is.False);
            Assert.That(episode.IsActionEnabled(0, 2), Is.True);
            Assert.That(episode.IsActionEnabled(1, 0), Is.True);
            Assert.That(episode.IsActionEnabled(1, 1), Is.True);
        }

        [TestCase(0, true)]
        [TestCase(1, false)]
        [TestCase(4, false)]
        [TestCase(5, true)]
        [TestCase(9, false)]
        [TestCase(10, true)]
        public void OnlyTenHertzStepsAdvancePolicyState(
            int academyStep,
            bool isDecision)
        {
            Assert.That(
                ResearchBasicContract.IsPolicyDecisionStep(academyStep),
                Is.EqualTo(isDecision));
        }

        private static int FindEpisodeIndexForTargetSlot(int targetSlot)
        {
            for (int index = 0; index < 1000; index++)
            {
                if (ResearchBasicEpisode.SampleTargetSlot(
                        ResearchBasicContract.ScenarioSeed,
                        index) == targetSlot)
                {
                    return index;
                }
            }

            throw new AssertionException("No deterministic target slot was found.");
        }
    }
}
