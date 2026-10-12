import json

from amlp.cli import main


def test_crc_command(capsys) -> None:
    assert main(["crc", "CMD,102,CONVEYOR_START,60"]) == 0
    assert capsys.readouterr().out.strip() == "C942"


def test_command_and_decode(capsys) -> None:
    assert main(["command", "--id", "102", "--name", "CONVEYOR_START", "--arg", "60"]) == 0
    encoded = capsys.readouterr().out.strip()

    assert main(["decode", encoded]) == 0
    decoded = json.loads(capsys.readouterr().out)
    assert decoded == {"type": "CMD", "fields": ["102", "CONVEYOR_START", "60"]}


def test_invalid_frame_returns_nonzero(capsys) -> None:
    assert main(["decode", "@CMD,102,CONVEYOR_START,60*0000"]) == 2
    assert "Error:" in capsys.readouterr().out


def test_generic_encode_matches_shared_vector(capsys) -> None:
    assert main(["encode", "--type", "ACK", "--field", "102", "--field", "OK"]) == 0
    assert capsys.readouterr().out == "@ACK,102,OK*22A0\r\n"
