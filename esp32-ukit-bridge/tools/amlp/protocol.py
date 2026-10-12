"""AMLP v1 ASCII framing defined by shared/protocol-spec/AMLP-v1.md."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

MAX_FRAME_LENGTH = 256
MAX_FIELDS = 12
MAX_PAYLOAD_FIELDS = MAX_FIELDS - 1
MAX_FIELD_LENGTH = 64
PARSER_TIMEOUT_MS = 250
_RESERVED = {",", "*", "@"}


class MessageType(str, Enum):
    CMD = "CMD"
    ACK = "ACK"
    TEL = "TEL"


class AckStatus(str, Enum):
    OK = "OK"
    UNKNOWN_COMMAND = "UNKNOWN_COMMAND"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class CommandId(str, Enum):
    CONVEYOR_START = "CONVEYOR_START"
    CONVEYOR_STOP = "CONVEYOR_STOP"
    PING = "PING"
    RESET = "RESET"
    SET_OUTPUT = "SET_OUTPUT"


class FrameError(ValueError):
    """Raised when an AMLP frame violates syntax, bounds, or CRC."""


@dataclass(frozen=True, slots=True)
class Frame:
    message_type: MessageType | str
    fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        try:
            message_type = MessageType(self.message_type)
        except ValueError as exc:
            raise FrameError(f"unsupported message type: {self.message_type!r}") from exc
        fields = tuple(self.fields)
        if len(fields) > MAX_PAYLOAD_FIELDS:
            raise FrameError(f"exceeds {MAX_PAYLOAD_FIELDS} payload fields")
        for field in fields:
            _validate_field(field)
        object.__setattr__(self, "message_type", message_type)
        object.__setattr__(self, "fields", fields)


def _validate_field(field: str) -> None:
    if not isinstance(field, str) or not field:
        raise FrameError("field must not be empty")
    try:
        encoded = field.encode("ascii")
    except UnicodeEncodeError as exc:
        raise FrameError("field must be printable 7-bit ASCII") from exc
    if len(encoded) > MAX_FIELD_LENGTH:
        raise FrameError(f"field exceeds {MAX_FIELD_LENGTH} bytes")
    if any(byte < 0x20 or byte > 0x7E or chr(byte) in _RESERVED for byte in encoded):
        raise FrameError("field contains a reserved AMLP character")


def crc16_ccitt_false(data: bytes | bytearray | memoryview) -> int:
    """Return CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF)."""

    crc = 0xFFFF
    for byte in bytes(data):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def encode_frame(frame: Frame) -> bytes:
    body = ",".join((frame.message_type.value, *frame.fields)).encode("ascii")
    crc = crc16_ccitt_false(body)
    encoded = b"@" + body + f"*{crc:04X}\r\n".encode("ascii")
    if len(encoded) > MAX_FRAME_LENGTH:
        raise FrameError("frame exceeds {MAX_FRAME_LENGTH} bytes")
    return encoded


def decode_frame(data: bytes | bytearray | memoryview) -> Frame:
    raw = bytes(data)
    if len(raw) > MAX_FRAME_LENGTH:
        raise FrameError("frame exceeds {MAX_FRAME_LENGTH} bytes")
    if raw.endswith(b"\r\n"):
        content = raw[:-2]
    elif raw.endswith(b"\n"):
        content = raw[:-1]
    else:
        raise FrameError("frame missing LF terminator")
    if b"\r" in content:
        raise FrameError("CR only allowed immediately before LF")
    if not content.startswith(b"@"):
        raise FrameError("frame missing @ marker")
    if content.count(b"*") != 1:
        raise FrameError("frame must contain exactly one *")

    body, crc_text = content[1:].rsplit(b"*", 1)
    if not body or len(crc_text) != 4 or any(byte not in b"0123456789ABCDEF" for byte in crc_text):
        raise FrameError("CRC text must be exactly 4 uppercase hex digits")
    try:
        text = body.decode("ascii")
    except UnicodeDecodeError as exc:
        raise FrameError("BODY must be ASCII") from exc

    expected_crc = int(crc_text, 16)
    actual_crc = crc16_ccitt_false(body)
    if actual_crc != expected_crc:
        raise FrameError(f"invalid CRC: expected {expected_crc:04X}, got {actual_crc:04X}")

    tokens = text.split(",")
    if len(tokens) > MAX_FIELDS:
        raise FrameError(f"exceeds {MAX_FIELDS} fields")
    if any(not token for token in tokens):
        raise FrameError("empty field is not allowed")
    for token in tokens:
        _validate_field(token)
    try:
        message_type = MessageType(tokens[0])
    except ValueError as exc:
        raise FrameError(f"unsupported message type: {tokens[0]}") from exc
    return Frame(message_type, tuple(tokens[1:]))


class StreamParser:
    """Incremental AMLP parser; a new @ restarts the current frame."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._last_byte_ms: int | None = None

    @property
    def active(self) -> bool:
        return bool(self._buffer)

    def reset(self) -> None:
        self._buffer.clear()
        self._last_byte_ms = None

    def check_timeout(self, now_ms: int) -> bool:
        if self.active and self._last_byte_ms is not None and (now_ms - self._last_byte_ms) >= PARSER_TIMEOUT_MS:
            self.reset()
            return True
        return False

    def feed(self, data: bytes | bytearray | memoryview, now_ms: int | None = None) -> list[Frame]:
        frames: list[Frame] = []
        for byte in bytes(data):
            if byte == ord("@"):
                self._buffer[:] = b"@"
                self._last_byte_ms = now_ms
                continue
            if not self._buffer:
                continue
            if len(self._buffer) >= MAX_FRAME_LENGTH:
                self.reset()
                continue
            self._buffer.append(byte)
            self._last_byte_ms = now_ms
            if byte == ord("\n"):
                candidate = bytes(self._buffer)
                self.reset()
                try:
                    frames.append(decode_frame(candidate))
                except FrameError:
                    pass
        return frames


def command_frame(correlation_id: int | str, command: str, arguments: Iterable[str] = ()) -> Frame:
    identifier = str(correlation_id)
    _parse_correlation_id(identifier)
    return Frame(MessageType.CMD, (identifier, command, *tuple(arguments)))


def ack_frame(correlation_id: int | str, status: AckStatus | str) -> Frame:
    identifier = str(correlation_id)
    _parse_correlation_id(identifier)
    status_value = status.value if isinstance(status, AckStatus) else status
    return Frame(MessageType.ACK, (identifier, status_value))


def telemetry_frame(metric: str, *values: object) -> Frame:
    return Frame(MessageType.TEL, (metric, *(str(value) for value in values)))


def _parse_correlation_id(value: str) -> int:
    if not value.isdigit() or value.startswith("0") or not 1 <= int(value) <= 0xFFFFFFFF:
        raise FrameError("correlation id must be a decimal number in 1..4294967295")
    return int(value)


def unpack_command(frame: Frame) -> tuple[int, str, tuple[str, ...]]:
    if frame.message_type is not MessageType.CMD or len(frame.fields) < 2:
        raise FrameError("CMD requires correlation_id and command")
    return _parse_correlation_id(frame.fields[0]), frame.fields[1], frame.fields[2:]


def unpack_ack(frame: Frame) -> tuple[int, str]:
    if frame.message_type is not MessageType.ACK or len(frame.fields) < 2:
        raise FrameError("ACK requires correlation_id and status")
    return _parse_correlation_id(frame.fields[0]), frame.fields[1]
