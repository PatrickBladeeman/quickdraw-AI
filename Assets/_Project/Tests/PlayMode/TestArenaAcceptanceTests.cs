using System.Collections;
using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

namespace QuickDraw.Tests.PlayMode
{
    public sealed class TestArenaAcceptanceTests
    {
        private static readonly Dictionary<string, Vector3> ExpectedGeometry = new Dictionary<string, Vector3>
        {
            { "Wall_North", new Vector3(12f, 2.8f, 0.2f) },
            { "Wall_South", new Vector3(12f, 2.8f, 0.2f) },
            { "Wall_East", new Vector3(0.2f, 2.8f, 12f) },
            { "Wall_West", new Vector3(0.2f, 2.8f, 12f) },
            { "OcclusionDivider", new Vector3(0.25f, 2.8f, 5f) },
            { "LowBlock", new Vector3(2f, 1f, 1.5f) }
        };

        private static readonly Dictionary<string, Vector3> ExpectedMarkers = new Dictionary<string, Vector3>
        {
            { "PlayerSpawn", new Vector3(0f, 1f, -4f) },
            { "NPCSpawn", new Vector3(0f, 0f, 3f) },
            { "PatrolPoint_A", new Vector3(-3f, 0f, 3f) },
            { "PatrolPoint_B", new Vector3(3f, 0f, 3f) },
            { "InteractionPoint", Vector3.zero }
        };

        [UnitySetUp]
        public IEnumerator SetUp()
        {
            SceneManager.LoadScene("Test_Arena", LoadSceneMode.Single);
            yield return null;

            CharacterController playerController = GameObject.Find("Player")?.GetComponent<CharacterController>();
            if (playerController != null)
            {
                playerController.enabled = false;
            }

            Physics.SyncTransforms();
        }

        [Test]
        public void SceneContainsOnlyThePrescribedTask3Fixtures()
        {
            GameObject floor = GameObject.Find("PB_floor");
            Assert.That(floor, Is.Not.Null, "The existing floor must remain.");
            Assert.That(GameObject.Find("Cube"), Is.Not.Null, "The existing ceiling must remain.");
            Assert.That(LayerMask.NameToLayer("NPC"), Is.EqualTo(8));

            Material floorMaterial = floor.GetComponent<Renderer>()?.sharedMaterial;
            Assert.That(floorMaterial, Is.Not.Null);
            Assert.That(floorMaterial.shader, Is.Not.Null);
            Assert.That(floorMaterial.shader.name, Is.Not.EqualTo("Hidden/InternalErrorShader"));

            Transform geometryRoot = RequireObject("ArenaGeometry").transform;
            Assert.That(geometryRoot.childCount, Is.EqualTo(ExpectedGeometry.Count));

            foreach (KeyValuePair<string, Vector3> expected in ExpectedGeometry)
            {
                Transform fixture = geometryRoot.Find(expected.Key);
                Assert.That(fixture, Is.Not.Null, $"Missing {expected.Key}.");
                Assert.That(fixture.localScale, Is.EqualTo(expected.Value));
                Assert.That(fixture.GetComponent<BoxCollider>(), Is.Not.Null);
                Assert.That(fixture.GetComponent<MeshRenderer>()?.sharedMaterial, Is.SameAs(floorMaterial));
                Assert.That(fixture.gameObject.isStatic, Is.True);
            }

            Transform markersRoot = RequireObject("ScenarioMarkers").transform;
            Assert.That(markersRoot.childCount, Is.EqualTo(ExpectedMarkers.Count));

            foreach (KeyValuePair<string, Vector3> expected in ExpectedMarkers)
            {
                Transform marker = markersRoot.Find(expected.Key);
                Assert.That(marker, Is.Not.Null, $"Missing {expected.Key}.");
                Assert.That(marker.localPosition, Is.EqualTo(expected.Value));
                Assert.That(marker.GetComponents<Component>().Length, Is.EqualTo(1), $"{expected.Key} must remain a marker-only transform.");
            }

            GameObject systems = RequireObject("Systems");
            Assert.That(systems.GetComponents<Component>().Length, Is.EqualTo(1), "Systems remains an empty container until diagnostics are ready.");
        }

        [Test]
        public void GeometrySupportsDirectPeripheralAndOccludedSightLines()
        {
            Vector3 playerEye = RequireObject("PlayerSpawn").transform.position + Vector3.up * 0.65f;
            Vector3 npcEye = RequireObject("NPCSpawn").transform.position + Vector3.up * 1.65f;

            Assert.That(Physics.Linecast(playerEye, npcEye, out RaycastHit directHit), Is.False,
                $"Direct lane was blocked by {directHit.collider?.name}.");

            Vector3 peripheralDirection = Quaternion.Euler(0f, 60f, 0f) * Vector3.back;
            Vector3 peripheralPosition = npcEye + peripheralDirection * 5f;
            float peripheralAngle = Vector3.Angle(Vector3.back, peripheralDirection);
            Assert.That(peripheralAngle, Is.GreaterThan(45f).And.LessThanOrEqualTo(70f));
            Assert.That(Physics.Linecast(npcEye, peripheralPosition, out RaycastHit peripheralHit), Is.False,
                $"Peripheral lane was blocked by {peripheralHit.collider?.name}.");

            Vector3 occludedTarget = new Vector3(3.5f, 1.65f, 2f);
            Assert.That(Physics.Linecast(playerEye, occludedTarget, out RaycastHit occludedHit), Is.True);
            Assert.That(occludedHit.collider.name, Is.EqualTo("OcclusionDivider"));

            AssertWallHit(new Vector3(0f, 1.4f, 0f), Vector3.forward * 7f, "Wall_North");
            AssertWallHit(new Vector3(0f, 1.4f, 0f), Vector3.back * 7f, "Wall_South");
            AssertWallHit(new Vector3(0f, 1.4f, -3f), Vector3.right * 7f, "Wall_East");
            AssertWallHit(new Vector3(0f, 1.4f, -3f), Vector3.left * 7f, "Wall_West");

            Collider divider = RequireObject("OcclusionDivider").GetComponent<Collider>();
            Collider lowBlock = RequireObject("LowBlock").GetComponent<Collider>();
            Assert.That(divider.bounds.min.y, Is.LessThanOrEqualTo(0.01f));
            Assert.That(divider.bounds.max.y, Is.GreaterThanOrEqualTo(2.79f));
            Assert.That(lowBlock.bounds.max.y, Is.EqualTo(1f).Within(0.01f));
        }

        private static GameObject RequireObject(string objectName)
        {
            GameObject result = GameObject.Find(objectName);
            Assert.That(result, Is.Not.Null, $"Missing {objectName}.");
            return result;
        }

        private static void AssertWallHit(Vector3 start, Vector3 direction, string expectedWall)
        {
            Assert.That(Physics.Linecast(start, start + direction, out RaycastHit hit), Is.True,
                $"No enclosing collider was found for {expectedWall}.");
            Assert.That(hit.collider.name, Is.EqualTo(expectedWall));
        }
    }
}
