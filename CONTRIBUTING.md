# Contributing to Smart Factory

Thank you for contributing to the Smart Factory — AIBOT Industrial Automation Platform.
This document explains how to work effectively and safely within this project.

---

## Claim Before You Start

1. **Open an issue** for the bug, feature or module you want to work on.
2. **Leave a comment** stating your intent and your expected timeline.
3. **Wait for acknowledgment** from a maintainer before writing code.
   - This prevents duplicated effort and ensures the work aligns with the
     physical hardware roadmap.
4. If you stop working on an issue, update the issue so someone else can take it.

---

## Branch Naming

```
feature/<issue-number>-<short-description>
fix/<issue-number>-<short-description>
docs/<issue-number>-<short-description>
chore/<issue-number>-<short-description>
```

**Examples:**

```
feature/42-amlp-telemetry-filtering
fix/67-mqtt-reconnect-deadlock
docs/89-architecture-overview
```

Use lowercase, hyphens only, no spaces. Keep `<short-description>` to 3–5 words.

---

## Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <short summary>

[optional body]

[optional footer: BREAKING CHANGE, Closes #<issue>]
```

### Types

| Type | When to use |
|---|---|
| `feat` | New feature or user-facing capability |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `test` | Adding or correcting tests |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf` | Performance improvement |
| `chore` | Maintenance, dependency updates, CI changes |
| `build` | Build system or CI configuration |

### Scope

Scope is the affected module or package. Use the subdirectory name:

```
feat(esp32-ukit-bridge): add telemetry rate limiting
fix(esp32-ukit-bridge): handle malformed JSON gracefully
docs: add quick-start section to root README
```

### Examples

```
feat(esp32-ukit-bridge): implement AMLP CONVEYOR_STOP command
fix(esp32-ukit-bridge): retry timer was not cleared after successful ACK
docs(architecture): add data flow diagrams
test(esp32-ukit-bridge): add CRC edge-case vectors
chore: bump pytest from 8.0 to 8.3
```

### Rules

- Summary is imperative mood, present tense: "add", not "added" or "adds".
- Summary does not end with a period.
- Body explains *what* and *why*, not *how*. Wrap at 72 characters.
- If the change is hardware-dependent, say so in the footer: `Hardware: requires ESP32-WROOM-32`.

---

## Pull Request Checklist

Before requesting a review, verify every item:

### Completeness

- [ ] All new code has type annotations (Python) or `//` comments (C/C++).
- [ ] New functions and classes have docstrings.
- [ ] Changes are covered by tests (unit tests for logic, integration tests for I/O).
- [ ] `esp32-ukit-bridge`: `python -m pytest tests/python` passes locally.
- [ ] `esp32-ukit-bridge`: `pio run -d ukit -e native` compiles without warnings.

### Documentation

- [ ] This PR updates `README.md` or module-level docs if behavior changed.
- [ ] The root `README.md` module status table is kept accurate.
- [ ] New protocol fields are documented in `docs/architecture/overview.md`
      and the relevant module's docs.

### Safety (mandatory for actuator / hardware changes)

- [ ] The change does not bypass MEGA-local safety enforcement.
- [ ] Emergency-stop behavior is unchanged or explicitly justified.
- [ ] New commands include a safety note in the PR description.

### Meta

- [ ] Branch is up to date with `main` (rebase, not merge).
- [ ] No debug print statements or commented-out code left in.
- [ ] Commit history is clean: one logical change per commit, rebase-squashed if needed.
- [ ] PR title follows the Conventional Commits format.

---

## Hardware Readiness Disclaimer

**Do not claim a feature is tested on real hardware unless you have physically run it.**

A common anti-pattern in industrial-automation projects:

```
feat(module): implement conveyor speed control
# Tested on simulator — need ESP32 + MEGA to verify
```

### Policy

- **Implemented** (green in the status table) means: code exists, unit/integration
  tests pass, and at least one contributor has run it on the target hardware.
- **Planned** means: research done, issue open, no hardware verification yet.
- **Blocked** means: external dependency (SDK, hardware sample, pinout) is missing.

If you cannot test on the physical factory, say explicitly in the PR:

```
# Tested via: Python simulator (TCP) + C99 native build
# Hardware verification needed: ESP32-WROOM-32 + uKit SDK
```

This sets correct expectations for reviewers and future maintainers.

---

## Development Environment

```bash
# Python 3.11+ required
python --version   # must be >= 3.11

# PlatformIO Core (install once)
python -m pip install --upgrade platformio

# esp32-ukit-bridge dev setup
cd esp32-ukit-bridge
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
python -m pip install -e ".[test]"

# Run tests
python -m pytest tests/python
pio run -d ukit -e native
```

---

## Code Style

| Language | Tool | Config |
|---|---|---|
| Python | `ruff` | `pyproject.toml` `[tool.ruff]` |
| C / C++ | `.clang-format` | in module root |
| Markdown | `markdownlint` | `.markdownlint.json` |

Run format checks before opening a PR:

```bash
ruff check .          # Python linting
ruff format --check .  # Python formatting
```

---

## Where to Ask

- **Bug reports / feature requests:** Open a GitHub issue.
- **Quick questions:** Open a GitHub Discussion.
- **Security concerns:** Do not file a public issue. Contact the maintainers
  directly (email in the module `README.md`).

---

## License

By contributing, you agree that your contributions will be licensed under the
MIT License used by this project. See individual module `LICENSE` files.
