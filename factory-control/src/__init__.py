"""Factory Control — Smart Factory Controller Simulator.

This package provides a deterministic factory controller simulator and
production state machine for offline testing and module adapter mocking.

Key components:
- ProductionStateMachine: Deterministic state transitions for factory production
- DeviceAdapter: Base class for module adapters (conveyor, robot, crane, etc.)
- FactorySimulator: Offline simulator for E2E testing without hardware

See README.md for architecture and safety constraints.
"""

__version__ = "0.1.0"
