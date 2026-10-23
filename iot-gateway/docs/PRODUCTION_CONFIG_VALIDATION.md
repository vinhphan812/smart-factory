# Production Configuration Validation (`iot-gateway`)

## 1. Startup Validation Gate
To prevent misconfigured production deployments from silently degrading security or runtime reliability, `GatewayConfig` implements strict production validation checks:
- **JWT Secret Enforcement:** `JWT_SECRET` must be set and $\ge$ 32 characters in production mode.
- **Database URL Validation:** `DATABASE_URL` must be explicitly configured.
- **MQTT Broker Authentication:** Non-localhost broker endpoints require valid `MQTT_USERNAME` and `MQTT_PASSWORD`.

## 2. Fail-Closed Behavior
If any required production configuration is missing or invalid:
- The service aborts startup with a descriptive error message (`ValueError`), ensuring container orchestrators (Kubernetes / Cloud Run) fail closed rather than starting in an insecure degraded state.
