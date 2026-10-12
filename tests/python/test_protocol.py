import pytest

from amlp.protocol import (
    Frame,
    FrameError,
    MessageType,
    StreamParser,
    crc16_ccitt_false,
    decode_frame,
    encode_frame,
)


def test_crc16_ccitt_false_standard_vector() -> None:
    assert crc16_ccitt_false(b"123456789") == 0x29B1


@pytest.mark.parametrize(
    ("frame", "wire"),
    [
        (
            Frame(MessageType.CMD, ("102", "CONVEYOR_START", "60")),
            b"@CMD,102,CONVEYOR_START,60*C942\r\n",
        ),
        (Frame(MessageType.ACK, ("102", "OK")), b"@ACK,102,OK*22A0\r\n"),
        (
            Frame(MessageType.TEL, ("CONVEYOR", "RUNNING", "60", "SENSOR1=1")),
            b"@TEL,CONVEYOR,RUNNING,60,SENSOR1=1*0942\r\n",
        ),
    ],
)
def test_shared_protocol_vectors(frame: Frame, wire: bytes) -> None:
    assert encode_frame(frame) == wire
    assert decode_frame(wire) == frame
    assert decode_frame(wire.replace(b"\r\n", b"\n")) == frame


def test_bad_crc_and_lowercase_crc_are_rejected() -> None:
    with pytest.raises(FrameError, match="invalid CRC"):
        decode_frame(b"@CMD,102,CONVEYOR_START,60*C943\r\n")
    with pytest.raises(FrameError, match="uppercase"):
        decode_frame(b"@CMD,102,CONVEYOR_START,60*c942\r\n")


def test_empty_and_reserved_fields_are_rejected() -> None:
    with pytest.raises(FrameError, match="must not be empty"):
        Frame(MessageType.CMD, ("102", "", "60"))
    with pytest.raises(FrameError, match="reserved"):
        Frame(MessageType.CMD, ("102", "BAD,FIELD"))


def test_stream_parser_handles_noise_chunks_and_restart_marker() -> None:
    first = encode_frame(Frame(MessageType.ACK, ("102", "OK")))
    second = encode_frame(
        Frame(MessageType.TEL, ("CONVEYOR", "RUNNING", "60", "SENSOR1=1"))
    )
    parser = StreamParser()

    assert parser.feed(b"noise" + first[:5]) == []
    assert parser.feed(b"@BROKEN" + second[:4]) == []
    frames = parser.feed(second[4:])

    assert frames == [
        Frame(MessageType.TEL, ("CONVEYOR", "RUNNING", "60", "SENSOR1=1"))
    ]


def test_stream_parser_timeout_discards_partial_frame() -> None:
    parser = StreamParser()
    parser.feed(b"@CMD,102", now_ms=100)
    assert parser.active
    assert not parser.check_timeout(349)
    assert parser.check_timeout(350)
    assert not parser.active
