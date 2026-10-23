# NGSI-LD JSON Schema Registry

JSON Schema validation files for Smart Factory NGSI-LD entities.

## Schema Files

| Schema | Description |
|--------|-------------|
| `base.json` | Shared NGSI-LD type definitions (Relationship, Property, GeoProperty, DateTime, etc.) |
| `geojson.json` | GeoJSON geometry definitions (Point, Polygon, LineString, etc.) |
| `device.json` | Device entity validation |
| `module.json` | Module entity validation |
| `job.json` | Job entity validation |
| `material.json` | Material entity validation |
| `operator.json` | Operator entity validation |
| `alert.json` | Alert entity validation |
| `incident.json` | Incident entity validation |
| `robot.json` | Robot entity validation (Issue #204, ADR-0016) |

## Usage

### Local Validation

Validate an entity against its schema:

```bash
# Using Python jsonschema library
python3 -c "
import json
import jsonschema

with open('device.json') as f:
    schema = json.load(f)

entity = {
    'id': 'urn:ngsi-ld:Device:bridge-001',
    'type': 'Device',
    'name': {'type': 'Text', 'value': 'ESP32 Bridge Unit 1'},
    'deviceType': {'type': 'Text', 'value': 'esp32_bridge'},
    'deviceId': {'type': 'Text', 'value': 'bridge-001'},
    'capabilities': {'type': 'Array', 'value': ['CONVEYOR_START', 'CONVEYOR_STOP']},
    'status': {'type': 'Text', 'value': 'online'},
    'createdAt': {'type': 'DateTime', 'value': '2026-10-20T10:00:00Z'}
}

jsonschema.validate(entity, schema)
print('Valid!')
"
```

### Orion-LD Integration

Schemas are referenced by the main entity schema document at `../ngsi-ld-entity-schema.md`.

### Validation in CI

```bash
# Install jsonschema
pip install jsonschema

# Validate all schemas (syntax check)
for schema in *.json; do
    python3 -c "import json; json.load(open('$schema'))" || exit 1
done
echo "All schemas are valid JSON"
```

## Schema Versions

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-10-20 | Initial schema definitions |

## References

- [JSON Schema Draft-07](https://json-schema.org/draft-07/draft-hypertext-json-schema-00)
- [NGSI-LD Specification](https://forge.etsi.org/rep/IoT/传感网络Specifications/blob/master/ngsi-ld.md)
