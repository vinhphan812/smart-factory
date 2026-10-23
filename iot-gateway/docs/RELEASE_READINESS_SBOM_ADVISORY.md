# Release Readiness: SBOM and Dependency Advisory Assessment (`iot-gateway`)

## 1. Dependency Pin and Version Policy
All dependencies for `iot-gateway` are strictly declared in `iot-gateway/pyproject.toml` with lower-bound constraints (`>=`) and safe upper-bound ceiling policies where applicable (e.g. `aiosqlite>=0.19,<1.0`, `cryptography>=42.0.0`).

## 2. CycloneDX SBOM Generation
A CycloneDX v1.5 JSON Software Bill of Materials (SBOM) is generated during CI and stored at `iot-gateway/sbom.json`.
- **Generation Command:** `python iot-gateway/scripts/generate_sbom.py`
- **Specification:** CycloneDX 1.5 JSON

## 3. Dependency Advisory Assessment
Dependency vulnerability scanning is integrated via `pip-audit` / OSV vulnerability checks in the release pipeline:
- **Command:** `pip-audit -r iot-gateway/pyproject.toml` (or scanning installed virtual environment packages).
- **Result:** No known vulnerabilities in introduced package versions (`paho-mqtt`, `websockets`, `uvicorn`, `fastapi`, `pydantic`, `sqlalchemy`, `aiosqlite`, `greenlet`, `aiohttp`, `cryptography`).
