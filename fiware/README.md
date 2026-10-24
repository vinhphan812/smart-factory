# FIWARE Orion-LD Context Broker Stack

This directory contains the Docker Compose configuration for deploying the FIWARE Orion-LD context broker with MongoDB as the backend and a JSON-LD context service for Smart Factory entities.

## Components

| Service | Image | Pinned digest | Port | Purpose |
|---------|-------|---------------|------|---------|
| **orion-ld** | `quay.io/fiware/orion-ld:1.5.0` | `sha256:dcb8c4100769b2a873b6d16c8ed501515fe3fb9ebde8d0fb4c3129ef07671bd2` | 1026 | NGSI-LD v1.3.1 Context Broker |
| **mongodb** | `mongo:7.0` | `sha256:c53852c00c23ca9f23fc39690350ffa9a80e3642fe8f96879726d8da0abe80a7` | 27017 | Orion-LD backend database |
| **json-ld-context** | `nginx:alpine` | `sha256:a3554c0d0b48177b1413c26e01f695334428020d9df01243fbae3e11cfd17417` | 3000 | JSON-LD @context definitions |

All three images are referenced by immutable digest in
`docker-compose.fiware.yml`; the tag above is kept for human readability only.

## Quick Start

```bash
# Start the FIWARE stack
docker compose -f docker-compose.fiware.yml up -d

# Check service status
docker compose -f docker-compose.fiware.yml ps

# View logs
docker compose -f docker-compose.fiware.yml logs -f orion-ld
```

## Health Checks

```bash
# Check Orion-LD health
curl http://localhost:1026/health

# Check JSON-LD context service
curl http://localhost:3000/health
```

## Configuration

Environment variables can be configured in the following files:

- `fiware/orion-ld.env` - Orion-LD configuration
- `fiware/mongodb.env` - MongoDB configuration

### Available Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ORION_LD_PORT` | 1026 | Orion-LD HTTP port |
| `MONGODB_PORT` | 27017 | MongoDB port |
| `JSON_LD_PORT` | 3000 | JSON-LD context HTTP port |
| `MONGODB_DB` | orion | Database name |
| `ORION_LD_LOG_LEVEL` | info | Logging level |

## NGSI-LD API Usage

### Create Entity

```bash
curl -X POST http://localhost:1026/ngsi-ld/v1/entities \
  -H "Content-Type: application/json" \
  -H "Link: <http://localhost:3000/contexts/smart-factory-context.jsonld>; rel=\"http://www.w3.org/ns/json-ld#context\"; type=\"application/ld+json\"" \
  -d '{
    "id": "urn:ngsi-ld:conveyor:001",
    "type": "conveyor",
    "operationalStatus": { "type": "Property", "value": "running" },
    "telemetry": { "type": "Property", "value": { "speed": 0.5, "itemsPerMin": 30 } }
  }'
```

### Query Entities

```bash
# Get all entities
curl http://localhost:1026/ngsi-ld/v1/entities

# Get specific entity
curl http://localhost:1026/ngsi-ld/v1/entities/urn:ngsi-ld:conveyor:001
```

### Subscribe to Changes

```bash
curl -X POST http://localhost:1026/ngsi-ld/v1/subscriptions \
  -H "Content-Type: application/json" \
  -d '{
    "id": "urn:ngsi-ld:subscription:001",
    "type": "Subscription",
    "notification": {
      "endpoint": {
        "uri": "http://iot-gateway:8080/notifications",
        "accept": "application/json"
      }
    },
    "q": "operationalStatus==running"
  }'
```

## CI Smoke Test

The included smoke test validates:

1. `docker compose config` passes (compose file validity)
2. Services start and reach healthy state
3. Orion-LD /health endpoint returns 200
4. JSON-LD context is accessible

Run locally:
```bash
# Validate compose file
docker compose -f docker-compose.fiware.yml config

# Full smoke test
docker compose -f docker-compose.fiware.yml up -d
sleep 45
curl -sf http://localhost:1026/health
docker compose -f docker-compose.fiware.yml down
```

## Data Persistence

MongoDB data is persisted in Docker volumes:
- `mongodb-data` - Database files
- `mongodb-config` - MongoDB configuration

Orion-LD logs are persisted in:
- `orionld-log` - Runtime logs

## Cleanup

```bash
# Stop services (preserve data)
docker compose -f docker-compose.fiware.yml down

# Stop and remove volumes (delete all data)
docker compose -f docker-compose.fiware.yml down -v
```

## References

- [Orion-LD Documentation](https://fiware-orion-ld.readthedocs.io/)
- [NGSI-LD Specification](https://www.etsi.org/deliver/etsi_gs/CIM/001_099/008/01.01.01_60/gs_CIM008v010101p.pdf)
- [FIWARE Academy - NGSI-LD](https://fiware-academy.readthedocs.io/en/latest/ngsi-ld/index.html)
