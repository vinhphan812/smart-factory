"""TCP simulator for the reference uKit AMLP endpoint."""

from __future__ import annotations

import argparse
from collections import OrderedDict
import socket
import time
from typing import Callable

from .protocol import (
    AckStatus,
    CommandId,
    Frame,
    FrameError,
    MessageType,
    StreamParser,
    ack_frame,
    encode_frame,
    telemetry_frame,
    unpack_command,
)


class SimulatorCore:
    """Application-profile handler with ACK and correlation-id dedupe."""

    def __init__(self, dedupe_size: int = 8) -> None:
        if dedupe_size < 1:
            raise ValueError("dedupe_size must be greater than 0")
        self.conveyor_running = False
        self.conveyor_speed = 0
        self.sensor1_active = True
        self._dedupe_size = dedupe_size
        self._results: OrderedDict[int, str] = OrderedDict()

    def handle_frame(self, frame: Frame) -> Frame | None:
        if frame.message_type is not MessageType.CMD:
            return None
        try:
            correlation_id, command, arguments = unpack_command(frame)
        except FrameError:
            # Cannot safely ACK if the correlation id is invalid.
            return None

        cached = self._results.get(correlation_id)
        if cached is not None:
            self._results.move_to_end(correlation_id)
            return ack_frame(correlation_id, cached)

        status = self._execute(command, arguments)
        self._results[correlation_id] = status.value
        self._results.move_to_end(correlation_id)
        while len(self._results) > self._dedupe_size:
            self._results.popitem(last=False)
        return ack_frame(correlation_id, status)

    def _execute(self, command: str, arguments: tuple[str, ...]) -> AckStatus:
        if command == CommandId.CONVEYOR_START.value:
            if len(arguments) != 1:
                return AckStatus.INVALID_ARGUMENT
            try:
                speed = int(arguments[0], 10)
            except ValueError:
                return AckStatus.INVALID_ARGUMENT
            if not 1 <= speed <= 100:
                return AckStatus.INVALID_ARGUMENT
            self.conveyor_running = True
            self.conveyor_speed = speed
            return AckStatus.OK
        if command == CommandId.CONVEYOR_STOP.value:
            if arguments:
                return AckStatus.INVALID_ARGUMENT
            self.conveyor_running = False
            self.conveyor_speed = 0
            return AckStatus.OK
        return AckStatus.UNKNOWN_COMMAND

    def telemetry(self) -> Frame:
        state = "RUNNING" if self.conveyor_running else "STOPPED"
        return telemetry_frame(
            "CONVEYOR",
            state,
            self.conveyor_speed,
            f"SENSOR1={int(self.sensor1_active)}",
        )


def serve(
    host: str,
    port: int,
    telemetry_interval: float,
    once: bool = False,
    log: Callable[[str], None] = print,
) -> None:
    """Serve AMLP over TCP for bridge development without physical uKit."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(1)
        log(f"AMLP simulator listening on {host}:{port}")

        while True:
            connection, address = server.accept()
            log(f"Connected: {address[0]}:{address[1]}")
            with connection:
                connection.settimeout(min(0.25, telemetry_interval))
                parser = StreamParser()
                core = SimulatorCore()
                next_telemetry = time.monotonic() + telemetry_interval

                while True:
                    try:
                        data = connection.recv(1024)
                    except socket.timeout:
                        data = None
                    except ConnectionError:
                        break

                    if data == b"":
                        break
                    if data:
                        for frame in parser.feed(data):
                            response = core.handle_frame(frame)
                            if response is not None:
                                connection.sendall(encode_frame(response))
                                log(f"ACK correlation_id={response.fields[0]}")

                    now = time.monotonic()
                    if now >= next_telemetry:
                        try:
                            connection.sendall(encode_frame(core.telemetry()))
                        except ConnectionError:
                            break
                        next_telemetry = now + telemetry_interval

            log("Client disconnected")
            if once:
                return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TCP uKit AMLP endpoint simulator")
    parser.add_argument("--host", default="127.0.0.1", help="bind address")
    parser.add_argument("--port", type=int, default=8765, help="TCP port")
    parser.add_argument("--telemetry-interval", type=float, default=1.0, help="telemetry period, seconds")
    parser.add_argument("--once", action="store_true", help="exit after first client")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 0 <= args.port <= 65535:
        raise SystemExit("--port must be in 0..65535")
    if args.telemetry_interval <= 0:
        raise SystemExit("--telemetry-interval must be greater than 0")
    try:
        serve(args.host, args.port, args.telemetry_interval, args.once)
    except KeyboardInterrupt:
        print("Simulator stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
