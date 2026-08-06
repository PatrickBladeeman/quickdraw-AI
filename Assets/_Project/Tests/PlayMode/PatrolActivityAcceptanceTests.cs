using System;
using System.Collections;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

namespace QuickDraw.Tests.PlayMode
{
    public sealed class PatrolActivityAcceptanceTests
    {
        private const string ActivityTypeName = "QuickDraw.AI.Activity.PatrolActivity, Assembly-CSharp";
        private Type _activityType;
        private GameObject _npc;
        private Component _activity;

        [UnitySetUp]
        public IEnumerator SetUp()
        {
            SceneManager.LoadScene("Test_Arena", LoadSceneMode.Single);
            yield return null;

            _activityType = Type.GetType(ActivityTypeName);
            Assert.That(_activityType, Is.Not.Null, $"Could not find {ActivityTypeName}.");

            _npc = GameObject.Find("NPC_01");
            Assert.That(_npc, Is.Not.Null);

            _activity = _npc.GetComponent(_activityType);
            Assert.That(_activity, Is.Not.Null);
            ((Behaviour)_activity).enabled = false;
            Invoke("ResetActivity");
        }

        [Test]
        public void SceneContainsConfiguredCapsuleNpcAndPatrolActivity()
        {
            Assert.That(UnityEngine.Object.FindObjectsByType(_activityType, FindObjectsInactive.Include, FindObjectsSortMode.None), Has.Length.EqualTo(1));
            Assert.That(_npc.layer, Is.EqualTo(LayerMask.NameToLayer("NPC")));
            Assert.That(_npc.GetComponent<CharacterController>(), Is.Not.Null);
            Assert.That(_npc.GetComponent<CapsuleCollider>(), Is.Null, "The NPC must not have overlapping capsule colliders.");
            Assert.That(_npc.GetComponent<MeshFilter>()?.sharedMesh, Is.Not.Null);
            Assert.That(
                _npc.GetComponent<MeshRenderer>()?.sharedMaterial,
                Is.SameAs(RequireObject("PB_floor").GetComponent<MeshRenderer>().sharedMaterial));

            Transform npcSpawn = RequireObject("NPCSpawn").transform;
            Transform patrolPointA = RequireObject("PatrolPoint_A").transform;
            Transform patrolPointB = RequireObject("PatrolPoint_B").transform;

            Assert.That(_npc.transform.position, Is.EqualTo(npcSpawn.position + Vector3.up));
            Assert.That(ReadField<Transform>("patrolPointA"), Is.SameAs(patrolPointA));
            Assert.That(ReadField<Transform>("patrolPointB"), Is.SameAs(patrolPointB));
            Assert.That(ReadProperty<string>("ActivityName"), Is.EqualTo("Patrol"));
            Assert.That(ReadProperty<bool>("IsRunning"), Is.True);
            Assert.That(ReadProperty<bool>("IsInterruptible"), Is.True);
            Assert.That(ReadProperty<Transform>("CurrentTarget"), Is.SameAs(patrolPointA));
            Assert.That(ReadProperty<float>("Progress"), Is.Zero);
            Assert.That(ReadProperty<float>("StartTime"), Is.GreaterThanOrEqualTo(0f));
        }

        [Test]
        public void PatrolRepeatsDeterministicallyBetweenBothMarkers()
        {
            Transform patrolPointA = RequireObject("PatrolPoint_A").transform;
            Transform patrolPointB = RequireObject("PatrolPoint_B").transform;

            Tick(0.5f);
            Assert.That(ReadProperty<float>("Progress"), Is.GreaterThan(0f).And.LessThan(1f));

            AdvanceUntilTargetChanges(patrolPointA);
            AssertHorizontalPosition(patrolPointA.position);
            Assert.That(ReadProperty<Transform>("CurrentTarget"), Is.SameAs(patrolPointB));

            AdvanceUntilTargetChanges(patrolPointB);
            AssertHorizontalPosition(patrolPointB.position);
            Assert.That(ReadProperty<Transform>("CurrentTarget"), Is.SameAs(patrolPointA));

            AdvanceUntilTargetChanges(patrolPointA);
            AssertHorizontalPosition(patrolPointA.position);
            Assert.That(ReadProperty<Transform>("CurrentTarget"), Is.SameAs(patrolPointB));
            Assert.That(ReadProperty<bool>("IsRunning"), Is.True);
        }

        [Test]
        public void InterruptResumeCancelAndResetLeaveConsistentState()
        {
            Tick(0.5f);
            Transform targetBeforeInterrupt = ReadProperty<Transform>("CurrentTarget");
            float progressBeforeInterrupt = ReadProperty<float>("Progress");

            Invoke("InterruptActivity", "AcceptanceTest");
            Vector3 interruptedPosition = _npc.transform.position;
            Tick(1f);

            Assert.That(_npc.transform.position, Is.EqualTo(interruptedPosition));
            Assert.That(ReadProperty<bool>("IsRunning"), Is.False);
            Assert.That(ReadProperty<bool>("IsInterrupted"), Is.True);
            Assert.That(ReadProperty<string>("InterruptionReason"), Is.EqualTo("AcceptanceTest"));
            Assert.That(ReadProperty<float>("InterruptionTime"), Is.GreaterThanOrEqualTo(0f));
            Assert.That(ReadProperty<Transform>("CurrentTarget"), Is.SameAs(targetBeforeInterrupt));
            Assert.That(ReadProperty<float>("Progress"), Is.EqualTo(progressBeforeInterrupt));

            Invoke("ResumeActivity");
            Assert.That(ReadProperty<bool>("IsRunning"), Is.True);
            Assert.That(ReadProperty<bool>("IsInterrupted"), Is.False);
            Assert.That(ReadProperty<float>("ResumeTime"), Is.GreaterThanOrEqualTo(0f));
            Tick(0.5f);
            Assert.That(_npc.transform.position, Is.Not.EqualTo(interruptedPosition));

            Invoke("CancelActivity");
            Vector3 cancelledPosition = _npc.transform.position;
            Invoke("ResumeActivity");
            Tick(1f);
            Assert.That(_npc.transform.position, Is.EqualTo(cancelledPosition));
            Assert.That(ReadProperty<bool>("IsRunning"), Is.False);
            Assert.That(ReadProperty<bool>("IsCancelled"), Is.True);

            Invoke("StartActivity");
            Assert.That(ReadProperty<bool>("IsRunning"), Is.True);
            Assert.That(ReadProperty<bool>("IsCancelled"), Is.False);

            Invoke("ResetActivity");
            Assert.That(_npc.transform.position, Is.EqualTo(RequireObject("NPCSpawn").transform.position + Vector3.up));
            Assert.That(ReadProperty<bool>("IsRunning"), Is.True);
            Assert.That(ReadProperty<bool>("IsInterrupted"), Is.False);
            Assert.That(ReadProperty<bool>("IsCancelled"), Is.False);
            Assert.That(ReadProperty<string>("InterruptionReason"), Is.Empty);
            Assert.That(ReadProperty<float>("Progress"), Is.Zero);
        }

        [Test]
        public void PatrolMovementStopsAtArenaWalls()
        {
            Transform patrolPointA = RequireObject("PatrolPoint_A").transform;
            patrolPointA.position = new Vector3(0f, 0f, 10f);
            Physics.SyncTransforms();
            Invoke("ResetActivity");

            for (int i = 0; i < 500; i++)
            {
                Tick(0.02f);
            }

            CharacterController npcController = _npc.GetComponent<CharacterController>();
            Collider northWall = RequireObject("Wall_North").GetComponent<Collider>();
            Assert.That(npcController.bounds.max.z, Is.LessThanOrEqualTo(northWall.bounds.min.z + 0.01f));
            Assert.That(ReadProperty<Transform>("CurrentTarget"), Is.SameAs(patrolPointA));
            Assert.That(ReadProperty<float>("Progress"), Is.LessThan(1f));
        }

        private void AdvanceUntilTargetChanges(Transform startingTarget)
        {
            for (int i = 0; i < 500 && ReadProperty<Transform>("CurrentTarget") == startingTarget; i++)
            {
                Tick(0.02f);
            }

            Assert.That(
                ReadProperty<Transform>("CurrentTarget"),
                Is.Not.SameAs(startingTarget),
                $"NPC remained at {_npc.transform.position} with progress {ReadProperty<float>("Progress"):0.000} while targeting {startingTarget.name}.");
        }

        private void Tick(float deltaTime)
        {
            Invoke("TickActivity", deltaTime);
        }

        private void Invoke(string methodName, params object[] arguments)
        {
            Type[] argumentTypes = Array.ConvertAll(arguments, argument => argument.GetType());
            MethodInfo method = _activityType.GetMethod(methodName, argumentTypes);
            Assert.That(method, Is.Not.Null, $"Missing method {methodName}.");
            method.Invoke(_activity, arguments);
        }

        private T ReadField<T>(string fieldName)
        {
            FieldInfo field = _activityType.GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
            Assert.That(field, Is.Not.Null, $"Missing field {fieldName}.");
            return (T)field.GetValue(_activity);
        }

        private T ReadProperty<T>(string propertyName)
        {
            PropertyInfo property = _activityType.GetProperty(propertyName, BindingFlags.Instance | BindingFlags.Public);
            Assert.That(property, Is.Not.Null, $"Missing property {propertyName}.");
            return (T)property.GetValue(_activity);
        }

        private void AssertHorizontalPosition(Vector3 expected)
        {
            Assert.That(_npc.transform.position.x, Is.EqualTo(expected.x).Within(0.001f));
            Assert.That(_npc.transform.position.z, Is.EqualTo(expected.z).Within(0.001f));
        }

        private static GameObject RequireObject(string objectName)
        {
            GameObject result = GameObject.Find(objectName);
            Assert.That(result, Is.Not.Null, $"Missing {objectName}.");
            return result;
        }
    }
}
