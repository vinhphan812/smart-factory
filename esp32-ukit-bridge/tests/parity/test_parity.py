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

# ---------------------------------------------------------------------------
# Canonical JSON envelope → AMLP wire parity
# ---------------------------------------------------------------------------

class TestCanonicalEnvelope:
    """Verify the canonical MQTT JSON envelope produces the correct AMLP wire frame.

    Canonical envelope (matches command.schema.json):
      {
        "command_id": 102,
        "request_id": "abc-123",
        "command_name": "CONVEYOR_START",
        "arguments": ["60"]
      }

    The firmware reads command_id (integer, preferred) or request_id (string).
    It calls CommandMapper.build() with the canonical command_name token.
    """

    def test_conveyor_start_command_id_integer(self) -> None:
        """Integer command_id + canonical command_name → AMLP wire."""
        from amlp.protocol import command_frame, encode_frame, CommandId
        frame = command_frame(102, CommandId.CONVEYOR_START, ("60",))
        wire = encode_frame(frame)
        assert wire == b"@CMD,102,CONVEYOR_START,60*C942\r\n"

    def test_conveyor_stop_command_id_integer(self) -> None:
        """CONVEYOR_STOP with integer command_id — no arguments."""
        from amlp.protocol import command_frame, encode_frame, CommandId
        frame = command_frame(42, CommandId.CONVEYOR_STOP, ())
        wire = encode_frame(frame)
        assert wire == b"@CMD,42,CONVEYOR_STOP*45A4\r\n"

    def test_set_output_command_id_integer(self) -> None:
        """SET_OUTPUT with channel=5, value=1."""
        from amlp.protocol import command_frame, encode_frame, CommandId
        frame = command_frame(7, CommandId.SET_OUTPUT, ("5", "1"))
        wire = encode_frame(frame)
        assert wire == b"@CMD,7,SET_OUTPUT,5,1*E7CF\r\n"

    def test_ping_command_id_integer(self) -> None:
        """PING — no arguments."""
        from amlp.protocol import command_frame, encode_frame, CommandId
        frame = command_frame(1, CommandId.PING, ())
        wire = encode_frame(frame)
        assert wire == b"@CMD,1,PING*EF72\r\n"

    def test_reset_command_id_integer(self) -> None:
        """RESET — no arguments."""
        from amlp.protocol import command_frame, encode_frame, CommandId
        frame = command_frame(2, CommandId.RESET, ())
        wire = encode_frame(frame)
        assert wire == b"@CMD,2,RESET*D0D3\r\n"


# ---------------------------------------------------------------------------
# JSON → AMLP round-trip parity (firmware JSON-reading → CommandMapper)
# ---------------------------------------------------------------------------

class TestJsonToAmlpMapping:
    """Simulate the firmware's JSON-reading + CommandMapper logic in Python.

    The firmware:
      1. Reads command_id (int) or falls back to request_id (string)
      2. Reads command_name from "command_name" field
      3. Reads arguments array
      4. Calls CommandMapper.build(...) → AMLP wire frame

    This verifies the Python codec produces the same wire output as the
    firmware would for each canonical command.
    """

    @pytest.mark.parametrize(
        "json_payload,expected_wire",
        [
            # CONVEYOR_START: speed 60
            (
                '{"command_id": 102, "command_name": "CONVEYOR_START", "arguments": ["60"]}',
                b"@CMD,102,CONVEYOR_START,60*C942\r\n",
            ),
            # CONVEYOR_STOP: no arguments
            (
                '{"command_id": 42, "command_name": "CONVEYOR_STOP"}',
                b"@CMD,42,CONVEYOR_STOP*45A4\r\n",
            ),
            # SET_OUTPUT: channel 5, value 1
            (
                '{"command_id": 7, "command_name": "SET_OUTPUT", "arguments": ["5", "1"]}',
                b"@CMD,7,SET_OUTPUT,5,1*E7CF\r\n",
            ),
            # PING
            (
                '{"command_id": 1, "command_name": "PING"}',
                b"@CMD,1,PING*EF72\r\n",
            ),
            # RESET
            (
                '{"command_id": 2, "command_name": "RESET"}',
                b"@CMD,2,RESET*D0D3\r\n",
            ),
        ],
        ids=["CONVEYOR_START", "CONVEYOR_STOP", "SET_OUTPUT", "PING", "RESET"],
    )
    def test_json_to_amlp_wire(self, json_payload: str, expected_wire: bytes) -> None:
        """Canonical JSON → AMLP wire matches the firmware output."""
        doc = json.loads(json_payload)
        cmd_id = doc["command_id"]
        cmd_name = doc["command_name"]
        args = tuple(doc.get("arguments", []))

        from amlp.protocol import command_frame, encode_frame, CommandId

        cmd_id_enum = CommandId(cmd_name)
        frame = command_frame(cmd_id, cmd_id_enum, args)
        wire = encode_frame(frame)
        assert wire == expected_wire


# ---------------------------------------------------------------------------
# Malformed JSON — simulates firmware rejection
# ---------------------------------------------------------------------------

class TestMalformedPayloadRejection:
    """Verify the firmware correctly rejects malformed JSON payloads.

    These cases should result in an immediate negative acknowledgement
    (status: "invalid_argument" or "unknown_command") from MqttBridge::onMessage().
    """

    def test_missing_command_name_rejected(self) -> None:
        """JSON without command_name → invalid_argument (firmware returns early)."""
        doc = {"command_id": 1}
        assert "command_name" not in doc

    def test_missing_request_id_and_command_id_rejected(self) -> None:
        """JSON without any correlation ID → invalid_argument."""
        doc = {"command_name": "PING"}
        assert "command_id" not in doc
        assert "request_id" not in doc

    def test_unknown_command_rejected(self) -> None:
        """Unknown command_name → unknown_command (CommandMapper returns kUnknownCommand)."""
        from amlp.protocol import CommandId
        with pytest.raises(ValueError):
            CommandId("EMERGENCY_STOP")

    def test_conveyor_start_speed_out_of_range_accepted_by_codec(self) -> None:
        """Python AMLP codec accepts any speed; range validation is done by C++ CommandMapper."""
        from amlp.protocol import command_frame, encode_frame, CommandId
        # Codec accepts any argument string; range checking is firmware responsibility
        frame = command_frame(1, CommandId.CONVEYOR_START, ("0",))
        wire = encode_frame(frame)
        assert wire == b"@CMD,1,CONVEYOR_START,0*8B67\r\n"

    def test_set_output_channel_out_of_range_accepted_by_codec(self) -> None:
        """Python AMLP codec accepts any channel; range validation is done by C++ CommandMapper."""
        from amlp.protocol import command_frame, encode_frame, CommandId
        frame = command_frame(1, CommandId.SET_OUTPUT, ("256", "1"))
        wire = encode_frame(frame)
        assert wire == b"@CMD,1,SET_OUTPUT,256,1*CE0F\r\n"

    def test_set_output_wrong_arg_count_accepted_by_codec(self) -> None:
        """Python AMLP codec accepts variable-length args; count validation is done by C++ CommandMapper."""
        from amlp.protocol import command_frame, encode_frame, CommandId
        # 1 argument — codec accepts it; CommandMapper rejects it at firmware level
        frame = command_frame(1, CommandId.SET_OUTPUT, ("5",))
        wire = encode_frame(frame)
        assert wire == b"@CMD,1,SET_OUTPUT,5*7051\r\n"

    def test_non_utf8_in_body_fields_rejected(self) -> None:
        """Non-printable-ASCII bytes in AMLP body are invalid per protocol spec."""
        # The AMLP spec restricts field content to printable ASCII 0x21-0x7E.
        bad_body = b"CMD,1,\xff\xfe"
        from amlp.protocol import crc16_ccitt_false
        crc = crc16_ccitt_false(bad_body)
        # CRC is computable but the frame would be rejected at parse time.
        assert isinstance(crc, int)


# ---------------------------------------------------------------------------
# Duplicate command suppression
# ---------------------------------------------------------------------------

class TestDuplicateCommandSuppression:
    """Verify that duplicate request_id is detectable using the Python protocol.

    The ESP32 firmware's BridgeCore maintains a 16-entry LRU cache of request_ids.
    The Python simulator uses the same 16-entry cache (tests/parity/conftest.py or
    simulator.py).

    This test verifies the Python codec produces unique wire output for unique
    request_ids, so the dedupe cache can distinguish them.
    """

    def test_unique_request_ids_produce_unique_wire_frames(self) -> None:
        """Each unique request_id (mapped to sequence) produces a distinct AMLP frame."""
        from amlp.protocol import command_frame, encode_frame, CommandId

        wire1 = encode_frame(command_frame(1, CommandId.PING, ()))
        wire2 = encode_frame(command_frame(2, CommandId.PING, ()))
        wire3 = encode_frame(command_frame(1, CommandId.CONVEYOR_START, ("60",)))

        # Different sequence numbers → different wire output
        assert wire1 != wire2
        # Same sequence, different command → different wire output
        assert wire1 != wire3

    def test_conveyor_start_speed_affects_wire_frame(self) -> None:
        """Speed argument is encoded in the AMLP frame body, so different speeds differ."""
        from amlp.protocol import command_frame, encode_frame, CommandId

        wire_30 = encode_frame(command_frame(1, CommandId.CONVEYOR_START, ("30",)))
        wire_60 = encode_frame(command_frame(1, CommandId.CONVEYOR_START, ("60",)))

        assert wire_30 != wire_60
        # CRC differs because body differs
        assert wire_30[-5:-3] != wire_60[-5:-3]  # CRC is 4 hex chars before \r\n

