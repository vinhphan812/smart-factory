"""Cross-implementation parity tests for AMLP JSON codec.

Loads canonical golden vectors from shared/protocol-spec/test-vectors.json
and verifies that the Python AMLP codec produces identical output to the
C++ (esp32) and C99 (ukit) implementations for every entry.

Canonical CRCs (from the spec):
  CMD,102,CONVEYOR_START,60 -> C942
  ACK,102,OK                -> 22A0
  TEL,CONVEYOR,RUNNING,60,SENSOR1=1 -> 0942
  CRC check: 123456789 -> 0x29B1
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amlp.protocol import (
    AckStatus,
    CommandId,
    Frame,
    MessageType,
    crc16_ccitt_false,
    decode_frame,
    encode_frame,
)

# Absolute path to the shared golden vectors file.
VECTORS_PATH = Path(__file__).resolve().parents[2] / "shared" / "protocol-spec" / "test-vectors.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_vectors() -> dict:
    """Load and parse the canonical test-vectors.json."""
    with open(VECTORS_PATH, encoding="ascii") as fh:
        return json.load(fh)


def build_frame(body: str) -> Frame:
    """Construct a Frame from its comma-separated body string.

    Handles the three AMLP message types:
      CMD,<id>,<cmd>[,<arg>...]
      ACK,<id>,<status>
      TEL,<metric>,<value>[,<value>...]
    """
    tokens = body.split(",")
    msg_type = MessageType(tokens[0])

    if msg_type is MessageType.CMD:
        return Frame(MessageType.CMD, tuple(tokens[1:]))
    elif msg_type is MessageType.ACK:
        return Frame(MessageType.ACK, tuple(tokens[1:]))
    else:  # TEL
        return Frame(MessageType.TEL, tuple(tokens[1:]))


# ---------------------------------------------------------------------------
# CRC-16/CCITT-FALSE parity
# ---------------------------------------------------------------------------

class TestCrcGoldenVectors:
    """CRC parity across C++, C99 and Python (no protocol framing)."""

    def test_crc_standard_polynomial_check(self) -> None:
        """CRC-16/CCITT-FALSE reference vector: 0x29B1 for 123456789."""
        assert crc16_ccitt_false(b"123456789") == 0x29B1

    @pytest.mark.parametrize(
        "vector",
        load_vectors()["vectors"],
        ids=[v["name"] for v in load_vectors()["vectors"]],
    )
    def test_body_crc_matches_golden(self, vector: dict) -> None:
        body_bytes = vector["body"].encode("ascii")
        expected_crc = int(vector["crc"], 16)
        assert crc16_ccitt_false(body_bytes) == expected_crc


# ---------------------------------------------------------------------------
# Round-trip encode / decode parity
# ---------------------------------------------------------------------------

class TestRoundTripParity:
    """Full encode→decode round-trip verified against every golden vector."""

    @pytest.mark.parametrize(
        "vector",
        load_vectors()["vectors"],
        ids=[v["name"] for v in load_vectors()["vectors"]],
    )
    def test_crlf_frame_roundtrip(self, vector: dict) -> None:
        """CRLF wire form: encode(Frame) == frameCrLf, decode(frameCrLf) == Frame."""
        frame = build_frame(vector["body"])
        encoded = encode_frame(frame)
        assert encoded == vector["frameCrLf"].encode("ascii")
        decoded = decode_frame(encoded)
        assert decoded == frame

    @pytest.mark.parametrize(
        "vector",
        load_vectors()["vectors"],
        ids=[v["name"] for v in load_vectors()["vectors"]],
    )
    def test_decode_accepts_lf_only(self, vector: dict) -> None:
        """Both C++ and C99 parsers accept bare \\n (no preceding \\r)."""
        frame = build_frame(vector["body"])
        # encode_frame always emits CRLF; the parsers additionally accept bare LF.
        lf_only_wire = vector["frameLf"].encode("ascii")
        decoded = decode_frame(lf_only_wire)
        assert decoded == frame

    @pytest.mark.parametrize(
        "vector",
        load_vectors()["vectors"],
        ids=[v["name"] for v in load_vectors()["vectors"]],
    )
    def test_decode_rejects_wrong_crc(self, vector: dict) -> None:
        """The malformed CRC case (C943 vs C942) must raise FrameError."""
        bad_frame = vector["frameCrLf"].replace(
            vector["crc"], f"{int(vector['crc'], 16) + 1:04X}"
        ).encode("ascii")
        with pytest.raises(Exception):  # FrameError with "invalid CRC"
            decode_frame(bad_frame)


# ---------------------------------------------------------------------------
# Cross-check: high-level helpers produce identical wire output
# ---------------------------------------------------------------------------

class TestHighLevelHelpers:
    """Verify command_frame / ack_frame / telemetry_frame match golden vectors."""

    def test_command_frame_matches_golden(self) -> None:
        from amlp.protocol import command_frame
        frame = command_frame(102, CommandId.CONVEYOR_START, ("60",))
        encoded = encode_frame(frame)
        assert encoded == b"@CMD,102,CONVEYOR_START,60*C942\r\n"

    def test_ack_frame_matches_golden(self) -> None:
        from amlp.protocol import ack_frame
        frame = ack_frame(102, AckStatus.OK)
        encoded = encode_frame(frame)
        assert encoded == b"@ACK,102,OK*22A0\r\n"

    def test_telemetry_frame_matches_golden(self) -> None:
        from amlp.protocol import telemetry_frame
        frame = telemetry_frame("CONVEYOR", "RUNNING", "60", "SENSOR1=1")
        encoded = encode_frame(frame)
        assert encoded == b"@TEL,CONVEYOR,RUNNING,60,SENSOR1=1*0942\r\n"
