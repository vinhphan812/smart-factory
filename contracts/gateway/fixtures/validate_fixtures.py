#!/usr/bin/env python3
"""Validate the Gateway northbound consumer fixture pack.

Checks, in order:

1. the pack validates against ``contracts/gateway/fixtures/fixture.schema.json``;
2. every canonical event in the pack validates against
   ``contracts/gateway/northbound-fanout.schema.json#/definitions/canonical_event``;
3. ``expected_state.unity`` and ``expected_state.react`` are equal apart from the
   ``consumer`` label (the parity rule, fixtures/README.md §4);
4. the TypeScript binding (``bindings/gatewayClient.ts``) reproduces
   ``expected_state.react`` exactly.

Usage::

    python contracts/gateway/fixtures/validate_fixtures.py

Exit code 0 = all checks passed. Exit code 1 = at least one check failed.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys

try:
    from jsonschema import Draft7Validator
except ImportError:  # pragma: no cover - dependency guard
    print("FAIL: the Python 'jsonschema' package is required", file=sys.stderr)
    sys.exit(1)


HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
FIXTURE_PATH = HERE / "northbound-fixture.v1.json"
FIXTURE_SCHEMA_PATH = HERE / "fixture.schema.json"
ENVELOPE_SCHEMA_PATH = HERE.parent / "northbound-fanout.schema.json"
TS_BINDING_CLI = HERE / "bindings" / "projection_cli.ts"


def load(path: pathlib.Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def check_schema(fixture: dict, schema: dict, label: str) -> list[str]:
    validator = Draft7Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(fixture), key=lambda e: list(e.path)):
        location = "/".join(str(part) for part in error.path) or "<root>"
        errors.append(f"{label}: {location}: {error.message}")
    return errors


def check_canonical_events(fixture: dict, envelope_schema: dict) -> list[str]:
    # The canonical_event definition uses local '#/definitions/...' references, so it
    # is validated through a wrapper that keeps the root definitions in scope.
    wrapper = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "definitions": envelope_schema["definitions"],
        "$ref": "#/definitions/canonical_event",
    }
    validator = Draft7Validator(wrapper)
    errors = []
    events = list(fixture["snapshot"]["events"])
    events += list(fixture["snapshot"]["per_device_latest"].values())
    events += [f["event"] for f in fixture["frames"] if f["frame_type"] == "event"]
    for event in events:
        for error in validator.iter_errors(event):
            location = "/".join(str(part) for part in error.path) or "<root>"
            errors.append(
                f"canonical_event {event.get('event_id', '<no id>')} "
                f"seq {event.get('sequence', '?')}: {location}: {error.message}"
            )
    return errors


def check_expected_state_parity(fixture: dict) -> list[str]:
    unity = fixture["expected_state"]["unity"]
    react = fixture["expected_state"]["react"]
    unity_cmp = dict(unity)
    react_cmp = dict(react)
    unity_cmp.pop("consumer", None)
    react_cmp.pop("consumer", None)
    if unity_cmp == react_cmp:
        return []
    return [
        "expected_state.unity and expected_state.react differ apart from the "
        "'consumer' label (parity rule, fixtures/README.md §4)"
    ]


def check_typescript_projection(fixture: dict) -> list[str]:
    node = shutil.which("node")
    if node is None:
        return ["node is not on PATH — cannot run the TypeScript projection check"]

    # Node exposes TypeScript type-stripping behind a flag on 22.x and by default on
    # 23+. Try the known-good invocations in order and use the first that works.
    invocations = [
        [node, "--experimental-strip-types", "--experimental-detect-module"],
        [node, "--experimental-strip-types"],
        [node],
    ]
    completed = None
    for invocation in invocations:
        command = invocation + [str(TS_BINDING_CLI), str(FIXTURE_PATH)]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
                check=False,
            )
        except OSError as exc:  # pragma: no cover - environment guard
            return [f"failed to launch node: {exc}"]
        if completed.returncode == 0:
            break

    if completed is None:
        return ["node is not on PATH — cannot run the TypeScript projection check"]
    if completed.returncode != 0:
        return [
            "the TypeScript projection failed to run:\n"
            f"  exit={completed.returncode}\n"
            f"  stdout={completed.stdout.strip()}\n"
            f"  stderr={completed.stderr.strip()}"
        ]

    try:
        projected = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return [f"the TypeScript projection did not print JSON: {exc}"]

    expected = fixture["expected_state"]["react"]
    if projected == expected:
        return []

    differences = []
    for key in sorted(set(projected) | set(expected)):
        if projected.get(key) != expected.get(key):
            differences.append(f"  - {key}:\n      projected={projected.get(key)}\n      expected ={expected.get(key)}")
    return ["the TypeScript projection does not match expected_state.react:\n" + "\n".join(differences)]


def main() -> int:
    fixture = load(FIXTURE_PATH)
    fixture_schema = load(FIXTURE_SCHEMA_PATH)
    envelope_schema = load(ENVELOPE_SCHEMA_PATH)

    failures: list[str] = []
    failures += check_schema(fixture, fixture_schema, "fixture.schema.json")
    failures += check_canonical_events(fixture, envelope_schema)
    failures += check_expected_state_parity(fixture)
    failures += check_typescript_projection(fixture)

    checks = [
        "pack validates against fixture.schema.json",
        "every canonical event validates against the northbound canonical_event schema",
        "expected_state.unity == expected_state.react (apart from the 'consumer' label)",
        "the TypeScript binding reproduces expected_state.react",
    ]
    for index, label in enumerate(checks, start=1):
        print(f"[{index}/4] {label}")

    if failures:
        print("\nFAILED:")
        for failure in failures:
            print(f"  * {failure}")
        return 1

    print("\nOK: all 4 fixture checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
