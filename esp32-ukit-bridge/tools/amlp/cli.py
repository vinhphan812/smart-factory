"""Command-line interface for AMLP ASCII frames."""

from __future__ import annotations

import argparse
import json

from .protocol import (
    Frame,
    FrameError,
    MessageType,
    command_frame,
    crc16_ccitt_false,
    decode_frame,
    encode_frame,
)


def _message_type(value: str) -> MessageType:
    try:
        return MessageType(value.upper())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("type must be CMD, ACK or TEL") from exc


def _frame_dict(frame: Frame) -> dict[str, object]:
    return {"type": frame.message_type.value, "fields": list(frame.fields)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="amlp", description="AMLP v1 ASCII tool")
    subparsers = parser.add_subparsers(dest="action", required=True)

    encode = subparsers.add_parser("encode", help="encode a frame from type and fields")
    encode.add_argument("--type", required=True, type=_message_type)
    encode.add_argument("--field", action="append", default=[])

    command = subparsers.add_parser("command", help="encode a CMD frame using the bridge profile")
    command.add_argument("--id", required=True, type=int, dest="correlation_id")
    command.add_argument("--name", required=True, help="e.g. CONVEYOR_START or CONVEYOR_STOP")
    command.add_argument("--arg", action="append", default=[])

    decode = subparsers.add_parser("decode", help="decode an ASCII frame")
    decode.add_argument("frame")

    crc = subparsers.add_parser("crc", help="calculate CRC-16/CCITT-FALSE")
    crc.add_argument("data", help="BODY ASCII, or hex when --hex is used")
    crc.add_argument("--hex", action="store_true", help="treat data as a hex string")

    simulate = subparsers.add_parser("simulate", help="run the uKit AMLP simulator over TCP")
    simulate.add_argument("--host", default="127.0.0.1")
    simulate.add_argument("--port", default=8765, type=int)
    simulate.add_argument("--telemetry-interval", default=1.0, type=float)
    simulate.add_argument("--once", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.action == "encode":
            print(encode_frame(Frame(args.type, tuple(args.field))).decode("ascii"), end="")
        elif args.action == "command":
            frame = command_frame(args.correlation_id, args.name, args.arg)
            print(encode_frame(frame).decode("ascii"), end="")
        elif args.action == "decode":
            raw = args.frame.encode("ascii")
            if not raw.endswith(b"\n"):
                raw += b"\n"
            print(json.dumps(_frame_dict(decode_frame(raw)), indent=2))
        elif args.action == "crc":
            if args.hex:
                try:
                    data = bytes.fromhex(args.data)
                except ValueError as exc:
                    raise FrameError("invalid hex string") from exc
            else:
                try:
                    data = args.data.encode("ascii")
                except UnicodeEncodeError as exc:
                    raise FrameError("CRC data must be ASCII or use --hex") from exc
            print(f"{crc16_ccitt_false(data):04X}")
        elif args.action == "simulate":
            from .simulator import serve

            if not 0 <= args.port <= 65535:
                raise FrameError("--port must be in 0..65535")
            if args.telemetry_interval <= 0:
                raise FrameError("--telemetry-interval must be greater than 0")
            serve(args.host, args.port, args.telemetry_interval, args.once)
    except (FrameError, OSError) as exc:
        print(f"Error: {exc}")
        return 2
    except KeyboardInterrupt:
        print("Stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
