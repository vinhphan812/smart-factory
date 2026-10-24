# Secrets Rotation Procedure (`iot-gateway`)

## 1. Secrets Scope
The gateway relies on sensitive configuration credentials:
- `JWT_SECRET`: Used for signing and verifying JWT authentication tokens (minimum 32 characters required).
- `MQTT_PASSWORD`: Authentication secret for MQTT broker communication.
- `SAFETY_OPERATOR_TOKEN`: Administrative token for safety-critical overrides and emergency stops.

## 2. Rotation Procedure (Zero-Downtime Rolling Rotation)
1. **Generate New Secret:** Create a cryptographically secure random secret (e.g. `openssl rand -hex 32`).
2. **Update Secret Store / Environment:** Update environment variables in the secure secrets manager (Kubernetes Secrets / Cloud Run Secret Manager) with `[REDACTED]` placeholders in templates.
3. **Rolling Deployment:**
   - Deploy new container instances configured with the new secret value.
   - Maintain dual-secret acceptance (if applicable) or perform rolling restart during scheduled maintenance window.
4. **Verification:** Validate `/api/auth/status` or health checks return 200 OK and successfully authenticate with the rotated credentials.

## 3. Fail-Closed Behavior
If `JWT_SECRET` is unset or shorter than 32 characters, the gateway fails closed at startup / authentication check with HTTP 503 Service Unavailable or startup failure, preventing insecure deployments.
