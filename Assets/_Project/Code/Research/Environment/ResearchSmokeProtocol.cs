using System;
using Newtonsoft.Json;

namespace QuickDraw.Research.Environment
{
    [JsonObject(MemberSerialization.OptIn)]
    public sealed class ResearchSmokeEnvelope
    {
        [JsonProperty("schema_version", Required = Required.Always, Order = 0)]
        public string SchemaVersion { get; set; }

        [JsonProperty("message_type", Required = Required.Always, Order = 1)]
        public string MessageType { get; set; }

        [JsonProperty("run_id", Required = Required.Always, Order = 2)]
        public string RunId { get; set; }

        [JsonProperty("episode_id", Required = Required.Always, Order = 3)]
        public int EpisodeId { get; set; }

        [JsonProperty("sequence", Required = Required.Always, Order = 4)]
        public int Sequence { get; set; }

        [JsonProperty("payload", Required = Required.Always, Order = 5)]
        public ResearchSmokePayload Payload { get; set; }
    }

    [JsonObject(MemberSerialization.OptIn)]
    public sealed class ResearchSmokePayload
    {
        [JsonProperty("seed", NullValueHandling = NullValueHandling.Ignore, Order = 0)]
        public int? Seed { get; set; }

        [JsonProperty("decision_limit", NullValueHandling = NullValueHandling.Ignore, Order = 1)]
        public int? DecisionLimit { get; set; }

        [JsonProperty("expected_end", NullValueHandling = NullValueHandling.Ignore, Order = 2)]
        public string ExpectedEnd { get; set; }

        [JsonProperty("contract_sha256", NullValueHandling = NullValueHandling.Ignore, Order = 3)]
        public string ContractSha256 { get; set; }

        [JsonProperty("unity_package_version", NullValueHandling = NullValueHandling.Ignore, Order = 4)]
        public string UnityPackageVersion { get; set; }

        [JsonProperty("observation_size", NullValueHandling = NullValueHandling.Ignore, Order = 5)]
        public int? ObservationSize { get; set; }

        [JsonProperty("discrete_branches", NullValueHandling = NullValueHandling.Ignore, Order = 6)]
        public int[] DiscreteBranches { get; set; }

        [JsonProperty("target", NullValueHandling = NullValueHandling.Ignore, Order = 7)]
        public int? Target { get; set; }

        [JsonProperty("step_count", NullValueHandling = NullValueHandling.Ignore, Order = 8)]
        public int? StepCount { get; set; }

        [JsonProperty("reason", NullValueHandling = NullValueHandling.Ignore, Order = 9)]
        public string Reason { get; set; }

        [JsonProperty("interrupted", NullValueHandling = NullValueHandling.Ignore, Order = 10)]
        public bool? Interrupted { get; set; }
    }

    public static class ResearchSmokeProtocol
    {
        public const string SchemaVersion = "quickdraw.research-side-channel.v1";
        public const string ChannelUuid = "fb54c591-19fe-502a-8714-7ebc3a49a0b5";
        public const string BehaviorName = "QuickDrawResearchSmoke";
        public const string ConfigureRun = "configure_run";
        public const string ConfigureEpisode = "configure_episode";
        public const string RunReady = "run_ready";
        public const string EpisodeStarted = "episode_started";
        public const string EpisodeEnded = "episode_ended";
        public const string InfrastructureError = "infrastructure_error";

        private static readonly JsonSerializerSettings SerializerSettings =
            new JsonSerializerSettings
            {
                MissingMemberHandling = MissingMemberHandling.Error,
                NullValueHandling = NullValueHandling.Ignore
            };

        public static bool TryDeserialize(
            string json,
            out ResearchSmokeEnvelope envelope,
            out string error)
        {
            envelope = null;
            error = string.Empty;

            if (string.IsNullOrWhiteSpace(json))
            {
                error = "The side-channel message is empty.";
                return false;
            }

            try
            {
                envelope = JsonConvert.DeserializeObject<ResearchSmokeEnvelope>(
                    json,
                    SerializerSettings);
            }
            catch (JsonException exception)
            {
                error = $"The side-channel message is not valid contract JSON: {exception.Message}";
                return false;
            }

            if (envelope == null || envelope.Payload == null)
            {
                error = "The side-channel envelope or payload is missing.";
                return false;
            }

            if (!string.Equals(
                    envelope.SchemaVersion,
                    SchemaVersion,
                    StringComparison.Ordinal))
            {
                error = $"Unsupported side-channel schema '{envelope.SchemaVersion}'.";
                return false;
            }

            if (string.IsNullOrWhiteSpace(envelope.MessageType) ||
                string.IsNullOrWhiteSpace(envelope.RunId) ||
                envelope.EpisodeId < 0 ||
                envelope.Sequence <= 0)
            {
                error = "The side-channel envelope contains an invalid identity or sequence.";
                return false;
            }

            return true;
        }

        public static string Serialize(ResearchSmokeEnvelope envelope)
        {
            if (envelope == null)
            {
                throw new ArgumentNullException(nameof(envelope));
            }

            return JsonConvert.SerializeObject(
                envelope,
                Formatting.None,
                SerializerSettings);
        }
    }
}
