// Reference C# parity harness for the Gateway northbound consumer fixture.
//
// Compiles the reference C# binding (../GatewayAdapter.cs), projects the recorded
// fixture, and asserts the result equals the `unity` section of the fixture's
// `expected_state` block.
//
// This is a REFERENCE ARTEFACT, not production code. It exists so the Unity and React
// projections of the same recording can be proven equivalent (contract §4, SPEC-4).
//
// Usage: dotnet run --project GatewayFixtureParity.csproj -- <fixture-path>
// Exit code 0 = parity holds. Exit code 1 = parity broken.

using System;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.Json.Serialization;
using SmartFactory.Contracts.Gateway.Fixtures;

internal static class Program
{
    private static int Main(string[] args)
    {
        if (args.Length < 1)
        {
            Console.Error.WriteLine("usage: GatewayFixtureParity <fixture-path>");
            return 2;
        }

        var fixturePath = args[0];
        var raw = File.ReadAllText(fixturePath);

        var options = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true,
            ReadCommentHandling = JsonCommentHandling.Skip,
            AllowTrailingCommas = true,
        };

        var fixture = JsonSerializer.Deserialize<Fixture>(raw, options);
        if (fixture is null)
        {
            Console.Error.WriteLine("FAIL: could not deserialize the fixture");
            return 2;
        }

        var projected = GatewayFixtureProjection.Project(fixture, "unity");

        var outOptions = new JsonSerializerOptions
        {
            DefaultIgnoreCondition = JsonIgnoreCondition.Never,
            WriteIndented = false,
        };
        var projectedNode = JsonNode.Parse(JsonSerializer.Serialize(projected, outOptions));

        JsonNode? expectedNode = null;
        using (var document = JsonDocument.Parse(raw))
        {
            if (document.RootElement.TryGetProperty("expected_state", out var expectedState) &&
                expectedState.TryGetProperty("unity", out var unity))
            {
                expectedNode = JsonNode.Parse(unity.GetRawText());
            }
        }

        if (projectedNode is null || expectedNode is null)
        {
            Console.Error.WriteLine("FAIL: the fixture does not carry an expected_state.unity section");
            return 2;
        }

        if (JsonNode.DeepEquals(projectedNode, expectedNode))
        {
            Console.WriteLine("C# parity: PASS — the C# projection equals expected_state.unity");
            return 0;
        }

        Console.Error.WriteLine("C# parity: FAIL — the C# projection does not equal expected_state.unity");
        Console.Error.WriteLine($"  projected: {projectedNode.ToJsonString()}");
        Console.Error.WriteLine($"  expected : {expectedNode.ToJsonString()}");
        return 1;
    }
}
