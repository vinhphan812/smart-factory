// Reference C# binding for the Gateway northbound consumer fixture.
//
// Implements the projection rule defined in contracts/gateway/fixtures/README.md §3
// against the recording in contracts/gateway/fixtures/northbound-fixture.v1.json.
//
// This is a REFERENCE ARTEFACT, not production code. The production Unity adapter lives in
// digital-twin/unity/Assets/Scripts/Adapters/GatewayAdapter.cs.
//
// Contract: contracts/gateway/northbound-fanout-contract.md §4 (SPEC-4).
// Status: Specification. Evidence level: L0 (contract / static).

using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace SmartFactory.Contracts.Gateway.Fixtures
{
    /// <summary>Connectivity visual state. Independent of data freshness.</summary>
    public enum Connectivity
    {
        Unknown,
        Online,
        Offline,
    }

    /// <summary>Freshness visual state of the latest applied telemetry event.</summary>
    public enum DataState
    {
        Unknown,
        Live,
        Stale,
        Uncertain,
    }

    public enum ClockDomain
    {
        Utc,
        DeviceMonotonic,
        Unknown,
    }

    public enum QualityStatus
    {
        Good,
        Uncertain,
        Degraded,
        Invalid,
        Unknown,
    }

    public sealed class Quality
    {
        [JsonPropertyName("status")]
        public string Status { get; set; } = "unknown";

        [JsonPropertyName("reason")]
        public string Reason { get; set; } = string.Empty;

        [JsonPropertyName("stale")]
        public bool Stale { get; set; }

        [JsonPropertyName("out_of_order")]
        public bool OutOfOrder { get; set; }

        [JsonPropertyName("clock_domain")]
        public string ClockDomain { get; set; } = "unknown";

        [JsonPropertyName("latency_ms")]
        public long LatencyMs { get; set; } = -1;
    }

    public sealed class CanonicalEvent
    {
        [JsonPropertyName("envelope_version")]
        public string? EnvelopeVersion { get; set; }

        [JsonPropertyName("event_id")]
        public string EventId { get; set; } = string.Empty;

        [JsonPropertyName("device_id")]
        public string DeviceId { get; set; } = string.Empty;

        [JsonPropertyName("module_id")]
        public string? ModuleId { get; set; }

        [JsonPropertyName("event_type")]
        public string EventType { get; set; } = string.Empty;

        [JsonPropertyName("sequence")]
        public long Sequence { get; set; }

        [JsonPropertyName("observed_at")]
        public long? ObservedAt { get; set; }

        [JsonPropertyName("received_at")]
        public string ReceivedAt { get; set; } = string.Empty;

        [JsonPropertyName("received_at_ms")]
        public long ReceivedAtMs { get; set; }

        [JsonPropertyName("boot_id")]
        public string? BootId { get; set; }

        [JsonPropertyName("units")]
        public Dictionary<string, string> Units { get; set; } = new();

        [JsonPropertyName("quality")]
        public Quality Quality { get; set; } = new();

        [JsonPropertyName("payload")]
        public JsonElement Payload { get; set; }
    }

    public sealed class StreamFrame
    {
        [JsonPropertyName("frame_type")]
        public string FrameType { get; set; } = string.Empty;

        [JsonPropertyName("event")]
        public CanonicalEvent? Event { get; set; }

        [JsonPropertyName("gap")]
        public JsonElement? Gap { get; set; }

        [JsonPropertyName("heartbeat")]
        public JsonElement? Heartbeat { get; set; }
    }

    public sealed class Snapshot
    {
        [JsonPropertyName("high_watermark")]
        public long HighWatermark { get; set; }

        [JsonPropertyName("snapshot_count")]
        public int SnapshotCount { get; set; }

        [JsonPropertyName("events")]
        public List<CanonicalEvent> Events { get; set; } = new();

        [JsonPropertyName("per_device_latest")]
        public Dictionary<string, CanonicalEvent> PerDeviceLatest { get; set; } = new();

        [JsonPropertyName("resync_required")]
        public bool ResyncRequired { get; set; }
    }

    public sealed class Fixture
    {
        [JsonPropertyName("fixture_version")]
        public string FixtureVersion { get; set; } = string.Empty;

        [JsonPropertyName("envelope_version")]
        public string EnvelopeVersion { get; set; } = string.Empty;

        [JsonPropertyName("snapshot")]
        public Snapshot Snapshot { get; set; } = new();

        [JsonPropertyName("frames")]
        public List<StreamFrame> Frames { get; set; } = new();
    }

    public sealed class ProjectedDeviceState
    {
        [JsonPropertyName("device_id")]
        public string DeviceId { get; set; } = string.Empty;

        [JsonPropertyName("connectivity")]
        public string Connectivity { get; set; } = "unknown";

        [JsonPropertyName("data_state")]
        public string DataState { get; set; } = "unknown";

        [JsonPropertyName("last_event_type")]
        public string? LastEventType { get; set; }

        [JsonPropertyName("last_sequence")]
        public long? LastSequence { get; set; }

        [JsonPropertyName("last_event_id")]
        public string? LastEventId { get; set; }

        [JsonPropertyName("boot_id")]
        public string? BootId { get; set; }

        [JsonPropertyName("observed_at")]
        public long? ObservedAt { get; set; }

        [JsonPropertyName("received_at")]
        public string? ReceivedAt { get; set; }

        [JsonPropertyName("clock_domain")]
        public string ClockDomain { get; set; } = "unknown";

        [JsonPropertyName("quality_status")]
        public string QualityStatus { get; set; } = "unknown";

        [JsonPropertyName("quality_reason")]
        public string QualityReason { get; set; } = string.Empty;

        [JsonPropertyName("units")]
        public Dictionary<string, string> Units { get; set; } = new();

        [JsonPropertyName("values")]
        public Dictionary<string, JsonElement> Values { get; set; } = new();

        [JsonPropertyName("payload_state")]
        public string? PayloadState { get; set; }
    }

    public sealed class ProjectedState
    {
        [JsonPropertyName("consumer")]
        public string Consumer { get; set; } = string.Empty;

        [JsonPropertyName("devices")]
        public Dictionary<string, ProjectedDeviceState> Devices { get; set; } = new();

        [JsonPropertyName("last_applied_sequence")]
        public long? LastAppliedSequence { get; set; }

        [JsonPropertyName("resync_required")]
        public bool ResyncRequired { get; set; }

        [JsonPropertyName("gap_detected")]
        public bool GapDetected { get; set; }

        [JsonPropertyName("applied_event_ids")]
        public List<string> AppliedEventIds { get; set; } = new();

        [JsonPropertyName("dropped_duplicate_event_ids")]
        public List<string> DroppedDuplicateEventIds { get; set; } = new();
    }

    /// <summary>
    /// Purely functional projection of a recorded Gateway read onto the consumer state.
    /// No I/O, no wall-clock reads, no randomness.
    /// </summary>
    public static class GatewayFixtureProjection
    {
        private sealed class Accumulator
        {
            public string DeviceId = string.Empty;
            public Connectivity Connectivity = Connectivity.Unknown;
            public DataState DataState = DataState.Unknown;
            public string? LastEventType;
            public long? LastSequence;
            public string? LastEventId;
            public string? BootId;
            public long? ObservedAt;
            public string? ReceivedAt;
            public ClockDomain ClockDomain = ClockDomain.Unknown;
            public QualityStatus QualityStatus = QualityStatus.Unknown;
            public string QualityReason = string.Empty;
            public Dictionary<string, string> Units = new();
            public Dictionary<string, JsonElement> Values = new();
            public string? PayloadState;
        }

        public static ProjectedState Project(Fixture fixture, string consumer)
        {
            // §3.1 — collect candidates: snapshot events first, then stream event frames.
            var candidates = new List<CanonicalEvent>();
            candidates.AddRange(fixture.Snapshot.Events);
            candidates.AddRange(fixture.Frames.Where(f => f.FrameType == "event").Select(f => f.Event!));

            // §3.2 — deduplicate by event_id, first occurrence wins.
            var seen = new HashSet<string>();
            var droppedDuplicates = new List<string>();
            var unique = new List<CanonicalEvent>();
            foreach (var e in candidates)
            {
                if (!seen.Add(e.EventId))
                {
                    droppedDuplicates.Add(e.EventId);
                    continue;
                }
                unique.Add(e);
            }

            // §3.3 — order by sequence, stable.
            var ordered = unique
                .Select((e, i) => (e, i))
                .OrderBy(x => x.e.Sequence)
                .ThenBy(x => x.i)
                .Select(x => x.e)
                .ToList();

            // §3.4 / §3.5 — project per device.
            var accumulators = new Dictionary<string, Accumulator>(StringComparer.Ordinal);
            var applied = new List<string>();
            long? lastApplied = null;

            foreach (var e in ordered)
            {
                if (!accumulators.TryGetValue(e.DeviceId, out var acc))
                {
                    acc = new Accumulator { DeviceId = e.DeviceId };
                    accumulators[e.DeviceId] = acc;
                }
                ApplyEvent(acc, e);
                applied.Add(e.EventId);
                lastApplied = e.Sequence;
            }

            // §3.6 — gap / resync.
            var gapDetected = fixture.Frames.Any(f => f.FrameType == "gap");
            var resyncRequired = fixture.Snapshot.ResyncRequired || gapDetected;

            var devices = new Dictionary<string, ProjectedDeviceState>(StringComparer.Ordinal);
            foreach (var key in accumulators.Keys.OrderBy(k => k, StringComparer.Ordinal))
            {
                var acc = accumulators[key];
                devices[key] = new ProjectedDeviceState
                {
                    DeviceId = acc.DeviceId,
                    Connectivity = acc.Connectivity.ToString().ToLowerInvariant(),
                    DataState = acc.DataState.ToString().ToLowerInvariant(),
                    LastEventType = acc.LastEventType,
                    LastSequence = acc.LastSequence,
                    LastEventId = acc.LastEventId,
                    BootId = acc.BootId,
                    ObservedAt = acc.ObservedAt,
                    ReceivedAt = acc.ReceivedAt,
                    ClockDomain = ClockDomainName(acc.ClockDomain),
                    QualityStatus = acc.QualityStatus.ToString().ToLowerInvariant(),
                    QualityReason = acc.QualityReason,
                    Units = acc.Units,
                    Values = acc.Values,
                    PayloadState = acc.PayloadState,
                };
            }

            return new ProjectedState
            {
                Consumer = consumer,
                Devices = devices,
                LastAppliedSequence = lastApplied,
                ResyncRequired = resyncRequired,
                GapDetected = gapDetected,
                AppliedEventIds = applied,
                DroppedDuplicateEventIds = droppedDuplicates,
            };
        }

        private static void ApplyEvent(Accumulator acc, CanonicalEvent e)
        {
            acc.LastEventType = e.EventType;
            acc.LastSequence = e.Sequence;
            acc.LastEventId = e.EventId;
            acc.BootId = e.BootId;
            acc.ReceivedAt = e.ReceivedAt;

            if (e.EventType == "status_online" || e.EventType == "status_offline")
            {
                acc.Connectivity = e.EventType == "status_online" ? Connectivity.Online : Connectivity.Offline;
                return;
            }

            if (e.EventType != "telemetry")
            {
                return;
            }

            acc.ObservedAt = e.ObservedAt;
            acc.ClockDomain = ParseClockDomain(e.Quality.ClockDomain);
            acc.QualityStatus = ParseQualityStatus(e.Quality.Status);
            acc.QualityReason = e.Quality.Reason ?? string.Empty;
            acc.Units = new Dictionary<string, string>(e.Units);
            acc.Values = DeriveValues(e.Payload);
            acc.PayloadState = DerivePayloadState(e.Payload);
            acc.DataState = DataStateFor(e);
        }

        /// <summary>§3.4 — data freshness from the latest applied telemetry event.</summary>
        private static DataState DataStateFor(CanonicalEvent e)
        {
            var status = ParseQualityStatus(e.Quality.Status);
            if (status == QualityStatus.Uncertain)
            {
                return DataState.Uncertain;
            }
            if (status == QualityStatus.Degraded || e.Quality.Stale)
            {
                return DataState.Stale;
            }
            if (status == QualityStatus.Good && !e.Quality.Stale)
            {
                return DataState.Live;
            }
            return DataState.Unknown;
        }

        /// <summary>§3.5 — derive the measurement map from payload.structured.</summary>
        private static Dictionary<string, JsonElement> DeriveValues(JsonElement payload)
        {
            var values = new Dictionary<string, JsonElement>(StringComparer.Ordinal);
            if (payload.ValueKind != JsonValueKind.Object)
            {
                return values;
            }
            if (!payload.TryGetProperty("structured", out var structured) ||
                structured.ValueKind != JsonValueKind.Object)
            {
                return values;
            }

            if (structured.TryGetProperty("state", out var state) &&
                state.ValueKind == JsonValueKind.String)
            {
                values["state"] = state.Clone();
            }
            if (structured.TryGetProperty("speed", out var speed) &&
                (speed.ValueKind == JsonValueKind.Number || speed.ValueKind == JsonValueKind.String))
            {
                values["speed"] = speed.Clone();
            }
            if (structured.TryGetProperty("sensors", out var sensors) &&
                sensors.ValueKind == JsonValueKind.Object)
            {
                if (sensors.TryGetProperty("temperature_centi_c", out var temperature) &&
                    (temperature.ValueKind == JsonValueKind.Number || temperature.ValueKind == JsonValueKind.String))
                {
                    values["temperature"] = temperature.Clone();
                }
                if (sensors.TryGetProperty("humidity_centi_percent", out var humidity) &&
                    (humidity.ValueKind == JsonValueKind.Number || humidity.ValueKind == JsonValueKind.String))
                {
                    values["humidity"] = humidity.Clone();
                }
            }
            return values;
        }

        private static string? DerivePayloadState(JsonElement payload)
        {
            if (payload.ValueKind != JsonValueKind.Object)
            {
                return null;
            }
            if (!payload.TryGetProperty("structured", out var structured) ||
                structured.ValueKind != JsonValueKind.Object)
            {
                return null;
            }
            if (structured.TryGetProperty("state", out var state) &&
                state.ValueKind == JsonValueKind.String)
            {
                return state.GetString();
            }
            return null;
        }

        private static ClockDomain ParseClockDomain(string? value) => value switch
        {
            "utc" => ClockDomain.Utc,
            "device_monotonic" => ClockDomain.DeviceMonotonic,
            _ => ClockDomain.Unknown,
        };

        private static string ClockDomainName(ClockDomain domain) => domain switch
        {
            ClockDomain.Utc => "utc",
            ClockDomain.DeviceMonotonic => "device_monotonic",
            _ => "unknown",
        };

        private static QualityStatus ParseQualityStatus(string? value) => value switch
        {
            "good" => QualityStatus.Good,
            "uncertain" => QualityStatus.Uncertain,
            "degraded" => QualityStatus.Degraded,
            "invalid" => QualityStatus.Invalid,
            _ => QualityStatus.Unknown,
        };
    }
}
