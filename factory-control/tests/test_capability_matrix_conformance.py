"""Conformance: the executable schema matches the L0 capability matrix.

Evidence level: L1 (executable cross-check of two committed documents).

This test parses ``contracts/physical/capability-matrix.md`` — the L0 source of
truth — and compares it with ``contracts/physical/capability-schema.v1.json``.
It proves that the executable schema invents no module, no sensor, no drive and
no command that the L0 matrix does not declare, and that the matrix declares
nothing the schema has silently dropped.

The matrix is parsed at test time; no expectation is hard-coded here beyond the
nine module identifiers and the IO type vocabulary of the matrix itself.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest

from capability_schema import CapabilitySchema, load_capability_schema

REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = REPO_ROOT / "contracts" / "physical" / "capability-matrix.md"

#: IO types the L0 matrix uses for real channels.
MATRIX_IO_TYPES = {
    "DI",
    "AI",
    "ENC",
    "DO",
    "SERVO",
    "MOTOR",
    "STEP",
    "ESTOP",
}

#: Matrix cell values that describe a channel type the schema encodes as a
#: composite placeholder or as a logical (non-GPIO) channel.
MATRIX_COMPOSITE_TYPES = {
    "SERVO or DO": "SERVO|DO",
    "logical input": "LOGICAL",
    "logical output": "LOGICAL",
}

MATRIX_MODULE_IDS = (
    "conveyor-01",
    "sorting-01",
    "tower-crane-01",
    "parking-01",
    "forklift-01",
    "dump-truck-01",
    "packaging-01",
    "brackets-01",
    "combine-01",
)

MODULE_HEADING = re.compile(r"^##\s+\d+\.\s+(?P<name>.+?)\s+—\s+`(?P<module_id>[a-z0-9-]+)`\s*$")
COMMAND_ROW = re.compile(r"^\|\s*`(?P<command>[A-Z_]+)`")


@pytest.fixture(scope="module")
def schema() -> CapabilitySchema:
    """The canonical capability schema."""
    return load_capability_schema()


@pytest.fixture(scope="module")
def matrix() -> Dict[str, Dict[str, List[str]]]:
    """The L0 matrix parsed into module -> {channels, commands}."""
    return _parse_matrix(MATRIX_PATH)


def _table_cells(line: str) -> List[str]:
    """Split a markdown table row into its raw cells."""
    if not line.startswith("|"):
        return []
    parts = line.split("|")
    # A leading and trailing pipe produce empty leading/trailing entries.
    return [cell.strip() for cell in parts[1:-1]]


def _is_table_separator(cell: str) -> bool:
    """Whether a cell is a markdown table separator or header label."""
    plain = cell.replace("`", "").strip()
    return not plain or plain in {"Channel", "Command", "Module"} or set(plain) <= set("-: ")


def _backticked_token(cell: str) -> Optional[str]:
    """Return the first backticked token of a cell, if any."""
    match = re.search(r"`([^`]+)`", cell)
    return match.group(1).strip() if match else None


def _parse_matrix(path: Path) -> Dict[str, Dict[str, List[str]]]:
    """Parse the module IO and command tables out of the L0 matrix."""
    parsed: Dict[str, Dict[str, List[str]]] = {}
    current: Dict[str, List[str]] | None = None
    section = ""

    for line in path.read_text(encoding="utf-8").splitlines():
        heading = MODULE_HEADING.match(line)
        if heading:
            current = {"channels": [], "commands": []}
            parsed[heading.group("module_id")] = current
            section = ""
            continue

        if current is None:
            continue

        if line.startswith("### "):
            section = line[4:].strip()
            continue

        cells = _table_cells(line)
        if not cells:
            continue

        if section == "IO Type":
            channel = _backticked_token(cells[0])
            if channel and not _is_table_separator(cells[0]):
                current["channels"].append(channel)
            continue

        if section == "Command Interface":
            token = _backticked_token(cells[0])
            if token and not _is_table_separator(cells[0]):
                # The matrix annotates some commands in prose after the token
                # (for example "GET_STATUS (future monitor)"); keep the token.
                current["commands"].append(token)
            continue

    return parsed


class TestMatrixConformance:
    """The executable schema declares exactly what the L0 matrix declares."""

    def test_matrix_declares_the_nine_modules(self, matrix) -> None:
        """The L0 matrix is the source of the nine-module catalogue."""
        assert len(matrix) == 9
        assert set(matrix) == {
            "conveyor-01",
            "sorting-01",
            "tower-crane-01",
            "parking-01",
            "forklift-01",
            "dump-truck-01",
            "packaging-01",
            "brackets-01",
            "combine-01",
        }

    def test_schema_modules_match_the_matrix_modules(
        self, schema: CapabilitySchema, matrix
    ) -> None:
        """The schema declares exactly the modules of the matrix."""
        assert set(schema.module_ids) == set(matrix)

    @pytest.mark.parametrize("module_id", MATRIX_MODULE_IDS)
    def test_no_invented_channels(self, schema: CapabilitySchema, matrix, module_id: str) -> None:
        """Every schema channel exists in the L0 matrix and vice versa."""
        module = schema.module(module_id)
        assert module is not None

        schema_channels = {signal["channel"] for signal in module.io_signals}
        matrix_channels = set(matrix[module_id]["channels"])

        assert schema_channels == matrix_channels, (
            f"{module_id}: schema channels {sorted(schema_channels)} != "
            f"matrix channels {sorted(matrix_channels)}"
        )

    @pytest.mark.parametrize("module_id", MATRIX_MODULE_IDS)
    def test_no_invented_commands(self, schema: CapabilitySchema, matrix, module_id: str) -> None:
        """Every schema capability exists in the L0 matrix and vice versa."""
        module = schema.module(module_id)
        assert module is not None

        schema_commands = set(module.capability_names)
        matrix_commands = set(matrix[module_id]["commands"])

        assert schema_commands == matrix_commands, (
            f"{module_id}: schema capabilities {sorted(schema_commands)} != "
            f"matrix commands {sorted(matrix_commands)}"
        )

    @pytest.mark.parametrize("module_id", MATRIX_MODULE_IDS)
    def test_channel_io_types_match_the_matrix(
        self, schema: CapabilitySchema, matrix, module_id: str
    ) -> None:
        """The declared IO type of every channel matches the matrix."""
        module = schema.module(module_id)
        assert module is not None

        matrix_types = _matrix_channel_types(MATRIX_PATH, module_id)
        for signal in module.io_signals:
            channel = signal["channel"]
            declared = matrix_types.get(channel)
            if declared is None:
                continue
            expected = MATRIX_COMPOSITE_TYPES.get(declared, declared)
            assert signal["io_type"] == expected, (
                f"{module_id}.{channel}: schema io_type {signal['io_type']!r} != "
                f"matrix io_type {expected!r}"
            )

    def test_no_channel_uses_an_invented_io_type(self, schema: CapabilitySchema) -> None:
        """Every IO type used by a channel is declared in the schema vocabulary."""
        for module in schema.modules:
            for signal in module.io_signals:
                assert signal["io_type"] in schema.io_types, (
                    f"{module.module_id}.{signal['channel']}: undeclared io_type "
                    f"{signal['io_type']!r}"
                )

    def test_no_pin_mapping_is_presented_as_verified(self, schema: CapabilitySchema) -> None:
        """No pin allocation is claimed as measured; hardware allocation is BLOCKED_L3."""
        for module in schema.modules:
            provenance = module.pin_mapping_provenance
            assert provenance["status"] != "VERIFIED"
            for channel, pin in provenance.get("declared_pins", {}).items():
                assert pin, f"{module.module_id}.{channel} declares an empty pin"


def _matrix_channel_types(path: Path, module_id: str) -> Dict[str, str]:
    """Return the IO type the matrix declares for each channel of a module."""
    types: Dict[str, str] = {}
    current_module = ""
    section = ""

    for line in path.read_text(encoding="utf-8").splitlines():
        heading = MODULE_HEADING.match(line)
        if heading:
            current_module = heading.group("module_id")
            section = ""
            continue

        if current_module != module_id:
            continue

        if line.startswith("### "):
            section = line[4:].strip()
            continue

        if section != "IO Type":
            continue

        cells = _table_cells(line)
        if not cells:
            continue

        channel = _backticked_token(cells[0])
        io_type_cell = cells[1] if len(cells) > 1 else ""
        # The matrix writes composite types as "SERVO or DO" across two
        # backticked tokens; strip the backticks to recover the whole type.
        io_type = io_type_cell.replace("`", "").strip()
        if channel and not _is_table_separator(cells[0]):
            types[channel] = io_type

    return types
