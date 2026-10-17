"""Pytest configuration for isolated safety gate tests.

This conftest only loads the safety_gate module without requiring
the full gateway dependencies (websockets, etc.).
"""

import pytest

# Safety gate tests don't need the full gateway - they're isolated
# Just import what's needed for safety_gate tests
