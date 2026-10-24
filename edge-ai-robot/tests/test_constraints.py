"""Static pin-closure test for edge-ai-robot (Issue #204 / ADR-0017).

The test is offline and dependency-resolution free by construction: it parses
`pyproject.toml` and `constraints.txt` from disk and compares the two. It never
contacts a package index, never builds a wheel and never imports the project
dependencies, so it is reproducible on an air-gapped runner.

Two invariants are asserted:

1. Every direct dependency declared in `pyproject.toml` — the runtime
   `dependencies` list, every `optional-dependencies` group and the
   `build-system.requires` list — has a matching exact (`==`) pin in
   `constraints.txt`, and that pin satisfies the declared version specifier.
2. Every entry in `constraints.txt` is an exact pin: no floating ranges, no
   unbounded entries and no duplicates, so the transitive closure stays
   reproducible.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

MODULE_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = MODULE_ROOT / "pyproject.toml"
CONSTRAINTS_PATH = MODULE_ROOT / "constraints.txt"

# An exact pin, e.g. "pydantic-core==2.50.1". Anything else (a range, a bare
# name, a URL) is rejected, because the closure must be fully reproducible.
PIN_PATTERN = re.compile(r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)==(?P<version>[A-Za-z0-9][A-Za-z0-9.*+!]*)$")


def _load_pyproject() -> dict:
    with PYPROJECT_PATH.open("rb") as handle:
        return tomllib.load(handle)


def _load_constraints() -> dict[str, str]:
    """Return the normalised name -> pinned version mapping of constraints.txt."""
    pins: dict[str, str] = {}
    for raw_line in CONSTRAINTS_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        match = PIN_PATTERN.match(line)
        assert match is not None, f"constraints.txt entry is not an exact pin: {raw_line!r}"
        pins[canonicalize_name(match.group("name"))] = match.group("version")
    return pins


def _direct_requirements() -> list[tuple[str, str]]:
    """Return (group, requirement string) for every direct dependency."""
    project = _load_pyproject()
    entries: list[tuple[str, str]] = []

    for requirement in project.get("project", {}).get("dependencies", []):
        entries.append(("runtime", requirement))

    for group, requirements in project.get("project", {}).get("optional-dependencies", {}).items():
        for requirement in requirements:
            entries.append((f"optional-dependencies.{group}", requirement))

    for requirement in project.get("build-system", {}).get("requires", []):
        entries.append(("build-system", requirement))

    return entries


DIRECT_REQUIREMENTS = _direct_requirements()
CONSTRAINT_PINS = _load_constraints()

_DIRECT_IDS = [f"{group}:{requirement}" for group, requirement in DIRECT_REQUIREMENTS]


def test_direct_requirements_are_discovered() -> None:
    """Guard against a silently empty comparison set."""
    assert DIRECT_REQUIREMENTS, "no direct dependencies parsed from pyproject.toml"
    groups = {group for group, _ in DIRECT_REQUIREMENTS}
    assert "runtime" in groups
    assert any(group.startswith("optional-dependencies.") for group in groups)


@pytest.mark.parametrize(("group", "requirement"), DIRECT_REQUIREMENTS, ids=_DIRECT_IDS)
def test_direct_dependency_has_exact_pin(group: str, requirement: str) -> None:
    """Every direct dependency is pinned with `==` in constraints.txt."""
    parsed = Requirement(requirement)
    name = canonicalize_name(parsed.name)
    assert name in CONSTRAINT_PINS, (
        f"{group} dependency {parsed.name!r} is not pinned in constraints.txt"
    )


@pytest.mark.parametrize(("group", "requirement"), DIRECT_REQUIREMENTS, ids=_DIRECT_IDS)
def test_pinned_version_satisfies_declared_specifier(group: str, requirement: str) -> None:
    """The pin recorded in constraints.txt satisfies the declared specifier."""
    parsed = Requirement(requirement)
    name = canonicalize_name(parsed.name)
    pinned = CONSTRAINT_PINS[name]
    assert pinned in parsed.specifier, (
        f"{group} dependency {parsed.name!r} is pinned at {pinned}, "
        f"which does not satisfy {parsed.specifier}"
    )


def test_every_constraints_entry_is_an_exact_pin() -> None:
    """No floating ranges, no unbounded entries in the closure."""
    offenders = []
    for raw_line in CONSTRAINTS_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if not PIN_PATTERN.match(line):
            offenders.append(raw_line)
    assert not offenders, f"constraints.txt contains non-pinned entries: {offenders}"


def test_constraints_have_no_duplicate_pins() -> None:
    """A package appears at most once, so the closure is unambiguous."""
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for raw_line in CONSTRAINTS_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        match = PIN_PATTERN.match(line)
        assert match is not None, f"constraints.txt entry is not an exact pin: {raw_line!r}"
        name = canonicalize_name(match.group("name"))
        if name in seen:
            duplicates.append(name)
        seen[name] = match.group("version")
    assert not duplicates, f"constraints.txt pins a package more than once: {sorted(set(duplicates))}"


def test_pinned_set_is_not_empty() -> None:
    """The closure is populated."""
    assert len(CONSTRAINT_PINS) > 0, "constraints.txt pins nothing"
