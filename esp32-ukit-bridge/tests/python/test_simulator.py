from amlp.protocol import AckStatus, Frame, MessageType, command_frame
from amlp.simulator import SimulatorCore


def test_conveyor_start_ack_and_telemetry() -> None:
    simulator = SimulatorCore()

    ack = simulator.handle_frame(command_frame(102, "CONVEYOR_START", ("60",)))

    assert ack == Frame(MessageType.ACK, ("102", AckStatus.OK.value))
    assert simulator.conveyor_running is True
    assert simulator.conveyor_speed == 60
    assert simulator.telemetry() == Frame(
        MessageType.TEL,
        ("CONVEYOR", "RUNNING", "60", "SENSOR1=1"),
    )


def test_duplicate_id_is_acknowledged_without_reexecution() -> None:
    simulator = SimulatorCore()
    first = command_frame(102, "CONVEYOR_START", ("60",))
    duplicate_with_different_body = command_frame(102, "CONVEYOR_START", ("20",))

    first_ack = simulator.handle_frame(first)
    duplicate_ack = simulator.handle_frame(duplicate_with_different_body)

    assert first_ack == duplicate_ack
    assert simulator.conveyor_speed == 60


def test_unknown_command_is_rejected() -> None:
    simulator = SimulatorCore()
    ack = simulator.handle_frame(command_frame(103, "ROBOT_START"))

    assert ack == Frame(MessageType.ACK, ("103", AckStatus.UNKNOWN_COMMAND.value))


def test_non_command_is_ignored() -> None:
    simulator = SimulatorCore()
    frame = Frame(MessageType.TEL, ("CONVEYOR", "STOPPED", "0", "SENSOR1=1"))
    assert simulator.handle_frame(frame) is None
