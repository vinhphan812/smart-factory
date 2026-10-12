# Developer onboarding and workflow

1. Read [project context](PROJECT_CONTEXT.md), [architecture](architecture/overview.md), [contracts](contracts-and-data.md), [AGENTS.md](../AGENTS.md) and relevant Issue.
2. Use current module-specific README and source as implementation truth. Check active PRs before changing files.
3. Claim an unassigned issue by comment `/claim` with plan, ETA, test design and blockers. This is a **manual convention** until a bot is installed; await assignment.

## Bridge local tests (from monorepo root)
```bash
cd esp32-ukit-bridge
python -m venv .venv
# activate .venv
python -m pip install -e ".[test]"
python -m pytest tests/python
python -m amlp simulate --telemetry-interval 1
```

From root:
```bash
pio test -d esp32-ukit-bridge/ukit -e native
pio run -d esp32-ukit-bridge/esp32 -e esp32-s3
```
PlatformIO availability, network dependency and serial hardware are environment-specific. Never mark a build/test successful without logs. Unreal Engine/toolchain version is not yet a locked repository-wide prerequisite; it must be pinned when its module is implemented.

## Git/PR discipline
Branch naming `feat/issue-<id>-short-name`, `fix/...`, `docs/...`; limit changes to issue scope. PR should contain purpose, implementation, linked issue, positive + negative tests, exact commands, screenshots/traces if UI, hardware evidence if relevant, safety evaluation, and docs/contract changes. Do not commit passwords, vendor-private SDK code or unreal build/cache products. Use Git LFS for approved 3D binaries when introduced.
