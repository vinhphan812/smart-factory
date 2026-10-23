"""Pytest configuration for the cross-module integration tests.

The integration tests span two modules (``iot-gateway`` and ``edge-ai-robot``).
Both source trees are added to ``sys.path`` so the scenarios can be executed
without installing the packages.

Evidence level: L2 (simulation) — see
``docs/testing-and-acceptance.md``.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

for module_src in (
    REPO_ROOT / "iot-gateway" / "src",
    REPO_ROOT / "edge-ai-robot" / "src",
):
    path = str(module_src)
    if path not in sys.path:
        sys.path.insert(0, path)
