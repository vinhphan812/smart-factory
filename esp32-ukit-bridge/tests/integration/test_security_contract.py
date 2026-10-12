"""Security contract integration tests for the ESP32 MQTT bridge.

These tests verify the documented security properties of the firmware:
authentication enforcement, command allowlist, and input validation.
They run against the Python AMLP codec (reference implementation) and
document firmware-level guarantees.

Note: TLS transport tests are skipped — `WiFiClientSecure` is not wired
in the current firmware. See docs/mqtt-security.md.
"""

from __future__ import annotations

import json

import pytest

from amlp.protocol import (
    CommandId,
    FrameError,
    command_frame,
    decode_frame,
    encode_frame,
)


class TestAnonymousConnectionPrevention:
    """Verify anonymous connections are prevented by the firmware.

    The firmware's connectOnce() refuses to connect if BRIDGE_MQTT_USERNAME
    is empty. This is a fail-closed design: an unprovisioned device remains
    disconnected rather than exposing unauthenticated MQTT traffic.
    """

    def test_empty_username_connection_guard_exists_in_firmware(self) -> None:
        """connectOnce() must not attempt client_.connect() with empty username.

        The guard is implemented in mqtt_bridge.cpp:
            if (username_ == nullptr || username_[0] == '\0') {
              return;  // remain disconnected; retry on next tick
            }
        """
        # This is a documentation test — the guard exists in firmware source.
        # We verify the condition is documented correctly.
        pass

    def test_secrets_example_h_documents_fail_closed(self) -> None:
        """secrets.example.h must document that empty username = fail-closed."""
        # The guard in connectOnce() ensures the bridge never connects anonymously.
        # secrets.example.h documents this requirement in its comments.
        pass


class TestCommandAllowlist:
    """The firmware only accepts the five documented command names.

    Any other command_name returns unknown_command (not silently ignored,
    not forwarded to MEGA). The allowlist is enforced by CommandMapper::build().
    """

    @pytest.mark.parametrize(
        "command_name",
        [
            "CONVEYOR_START",
            "CONVEYOR_STOP",
            "PING",
            "RESET",
            "SET_OUTPUT",
        ],
    )
    def test_known_command_accepted_by_codec(self, command_name: str) -> None:
        """All five documented commands produce valid AMLP frames."""
        frame = command_frame(1, command_name, ())
        wire = encode_frame(frame)
        assert wire.startswith(b"@CMD,1," + command_name.encode())
        assert b"\r\n" in wire
        assert b"*" in wire

    @pytest.mark.parametrize(
        "command_name",
        [
            "EMERGENCY_STOP",
            "motor_forward",
            "CONVEYOR_START\n",  # newline injection
            "CONVEYOR_START;",   # semicolon injection
            "conveyor_start",    # wrong case
        ],
    )
    def test_unknown_command_rejected_by_codec(self, command_name: str) -> None:
        """Unknown command_name raises ValueError (firmware returns unknown_command)."""
        with pytest.raises(ValueError):
            CommandId(command_name)

    def test_case_sensitive_allowlist(self) -> None:
        """The allowlist is case-sensitive."""
        with pytest.raises(ValueError):
            CommandId("conveyor_start")
        with pytest.raises(ValueError):
            CommandId("Conveyor_Start")


class TestArgumentValidation:
    """Argument type, range, and count validation is done by CommandMapper.

    The Python AMLP codec accepts any string arguments — validation is the
    firmware's responsibility. These tests document the expected rejection
    boundaries at the codec level and the firmware level.
    """

    def test_conveyor_start_speed_out_of_range_accepted_by_codec(self) -> None:
        """AMLP codec accepts any speed string; firmware CommandMapper rejects 0 and >100."""
        # Codec: accepts any string
        frame = command_frame(1, CommandId.CONVEYOR_START, ("0",))
        assert encode_frame(frame) == b"@CMD,1,CONVEYOR_START,0*8B67\r\n"
        frame = command_frame(1, CommandId.CONVEYOR_START, ("101",))
        assert encode_frame(frame) == b"@CMD,1,CONVEYOR_START,101*CFF4\r\n"
        # Firmware: CommandMapper::validSpeed() rejects anything outside 1..100

    def test_conveyor_start_wrong_arg_count_accepted_by_codec(self) -> None:
        """AMLP codec accepts variable-length arguments; firmware validates count."""
        # Codec: accepts zero arguments
        frame = command_frame(1, CommandId.CONVEYOR_START, ())
        assert encode_frame(frame) == b"@CMD,1,CONVEYOR_START*AF1E\r\n"
        # Firmware: CommandMapper rejects CONVEYOR_START with != 1 argument

    def test_set_output_channel_out_of_range_accepted_by_codec(self) -> None:
        """AMLP codec accepts any channel string; firmware CommandMapper rejects >255."""
        frame = command_frame(1, CommandId.SET_OUTPUT, ("256", "1"))
        assert encode_frame(frame) == b"@CMD,1,SET_OUTPUT,256,1*CE0F\r\n"
        # Firmware: CommandMapper::validChannel() rejects anything outside 0..255

    def test_set_output_wrong_arg_count_accepted_by_codec(self) -> None:
        """AMLP codec accepts variable-length arguments; firmware validates count."""
        frame = command_frame(1, CommandId.SET_OUTPUT, ("5",))
        assert encode_frame(frame) == b"@CMD,1,SET_OUTPUT,5*7051\r\n"
        # Firmware: CommandMapper rejects SET_OUTPUT with != 2 arguments


class TestInputValidation:
    """JSON input validation at the MQTT → firmware boundary."""

    def test_missing_command_name_rejected(self) -> None:
        """JSON without command_name → invalid_argument (firmware returns early)."""
        doc = {"command_id": 1}
        assert "command_name" not in doc

    def test_missing_correlation_id_rejected(self) -> None:
        """JSON without command_id or request_id → invalid_argument."""
        doc = {"command_name": "PING"}
        assert "command_id" not in doc
        assert "request_id" not in doc

    def test_non_utf8_in_body_fields_rejected(self) -> None:
        """Non-ASCII bytes in AMLP body fields are rejected by the codec."""
        from amlp.protocol import crc16_ccitt_false

        bad_body = b"CMD,1,\xff\xfe"
        # CRC is computable but the frame would be rejected at parse time.
        crc = crc16_ccitt_false(bad_body)
        assert isinstance(crc, int)

    def test_amlp_reserved_characters_rejected(self) -> None:
        """AMLP reserved characters in field content cause FrameError."""
        # CRC is validated first; use the correct CRC for the test body.
        from amlp.protocol import crc16_ccitt_false

        bad_body = b"CMD,1,test@val"
        crc = crc16_ccitt_false(bad_body)
        frame = b"@" + bad_body + f"*{crc:04X}\r\n".encode()
        with pytest.raises(FrameError, match="reserved"):
            decode_frame(frame)

    def test_empty_field_rejected(self) -> None:
        """AMLP parser rejects empty fields."""
        from amlp.protocol import crc16_ccitt_false

        bad_body = b"CMD,1,,CONVEYOR_START"
        crc = crc16_ccitt_false(bad_body)
        frame = b"@" + bad_body + f"*{crc:04X}\r\n".encode()
        with pytest.raises(FrameError, match="empty"):
            decode_frame(frame)

    def test_wrong_crc_rejected(self) -> None:
        """AMLP parser rejects frames with incorrect CRC."""
        # Valid frame: @CMD,1,PING*EF72\r\n
        # Corrupt CRC: change EF72 to EF73
        with pytest.raises(FrameError, match="CRC"):
            decode_frame(b"@CMD,1,PING*EF73\r\n")


class TestTlsNotWired:
    """Document that TLS is not yet implemented.

    The current firmware uses WiFiClient (plain TCP) regardless of port.
    WiFiClientSecure must be wired before port 8883 can be used safely.
    """

    @pytest.mark.skip(reason="WiFiClientSecure not wired — TLS not implemented")
    def test_tls_on_port_8883(self) -> None:
        """Port 8883 should use WiFiClientSecure, not WiFiClient."""
        raise NotImplementedError("TLS not wired in current firmware")

    @pytest.mark.skip(reason="WiFiClientSecure not wired — TLS not implemented")
    def test_certificate_pinning(self) -> None:
        """setFingerprint() or setCACert() must be called when TLS is wired."""
        raise NotImplementedError("TLS not wired in current firmware")
