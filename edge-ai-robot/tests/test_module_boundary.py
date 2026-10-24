"""The robot module must never import the gateway (ADR-0001, ADR-0017).

This turns a docstring rule into an executable check.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROBOT_SRC = Path(__file__).resolve().parents[1] / "src" / "edge_ai_robot"


def _python_files() -> list[Path]:
    return sorted(ROBOT_SRC.rglob("*.py"))


def test_robot_package_has_sources() -> None:
    assert _python_files(), "no sources found under edge-ai-robot/src/edge_ai_robot"


def test_robot_package_never_imports_iot_gateway() -> None:
    offenders: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name == "iot_gateway" or name.startswith("iot_gateway."):
                    offenders.append(f"{path.relative_to(ROBOT_SRC)}: {name}")
    assert not offenders, (
        "edge-ai-robot must not import iot_gateway (ADR-0001 module boundary): "
        + "; ".join(offenders)
    )
