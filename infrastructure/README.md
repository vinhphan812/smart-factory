# Infrastructure — Smart Factory

**Status: PLANNED** | Related issues: #17 #41 #51

## Purpose

Reproducible local development and deployment: Docker Compose stack, secrets management, environment configuration, MQTT broker, recovery procedures and backup scripts.

## Scope

- `docker-compose.yml` for the full local stack (broker, gateway, optional Twin, optional dashboard)
- `.env.example` and `secrets/` with **no real credentials**
- Backup and recovery runbooks
- CI runner environment setup

## Module structure

```
infrastructure/
├── README.md            ← this file
├── compose/             ← Docker Compose files
├── config/              ← broker, gateway config templates
├── secrets/             ← .gitignored secrets examples
└── scripts/             ← local deployment, backup, recovery
```

## Security constraints

- No real credentials, API keys or identifiable participant data in the repository.
- Secrets are managed via environment variables or a secrets manager; never committed.
- MQTT broker uses credentials from environment, not hardcoded in config.

## Readiness

**PLANNED.** Local stack not yet defined. `iot-gateway/` and `esp32-ukit-bridge/` must be stable before infra is finalized.