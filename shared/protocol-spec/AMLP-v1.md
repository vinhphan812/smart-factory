# AMLP v1

AMLP v1 is a small ASCII framing protocol for command, acknowledgement, and telemetry messages. Its canonical wire form is:

```text
@BODY*CRC4\r\n
```

Receivers MUST also accept an LF-only terminator (`\n`). Senders MUST emit the canonical CRLF terminator (`\r\n`).

## Frame grammar

```abnf
frame      = "@" body "*" crc4 (CR LF / LF)
body       = type *( "," field )
type       = "CMD" / "ACK" / "TEL"
field      = 1*64field-char
field-char = %x20-29 / %x2B / %x2D-3F / %x41-7E
crc4       = 4HEXDIG-UPPER
HEXDIG-UPPER = DIGIT / %x41-46
```

`field-char` is printable ASCII except comma (`,`), asterisk (`*`), and at sign (`@`). CR and LF are also forbidden inside BODY. AMLP v1 has no escaping or quoting. A value containing a reserved or non-ASCII character must be represented by an application-defined encoding before it is placed in a field.

Empty fields are invalid. The type token counts toward the field limit.

## Message types

- `CMD`: a command sent to a device or service.
- `ACK`: an acknowledgement or command result.
- `TEL`: telemetry or state reported by a device or service.

AMLP defines framing and the three type tokens. The meaning and ordering of payload fields are application-profile concerns. Profiles should normally put a correlation or sequence identifier immediately after `CMD` and `ACK`.

## CRC

CRC4 is the uppercase, four-character hexadecimal rendering of CRC-16/CCITT-FALSE calculated over the exact ASCII bytes of BODY only. The leading `@`, `*`, CRC text, and line terminator are not included.

| Parameter | Value |
|---|---:|
| Width | 16 |
| Polynomial | `0x1021` |
| Initial value | `0xFFFF` |
| Reflect input | false |
| Reflect output | false |
| Final XOR | `0x0000` |
| Check value for `123456789` | `0x29B1` |

Examples:

```text
@CMD,102,CONVEYOR_START,60*C942\r\n
@ACK,102,OK*22A0\r\n
@TEL,CONVEYOR,RUNNING,60,SENSOR1=1*0942\r\n
```

## Limits

- Maximum complete wire frame: 256 bytes, including `@`, `*`, four CRC characters, and line terminator.
- Maximum fields: 12 total, including the type token; therefore at most 11 payload fields.
- Maximum field length: 64 bytes.
- Encoding: printable 7-bit ASCII under the restrictions above.

A receiver MUST reject a frame that exceeds any limit. It must not truncate a frame, field, or CRC.

## Incremental receiver behavior

A receiver can operate with a fixed 256-byte buffer:

1. Ignore bytes until `@` is received.
2. `@` starts a new frame. If `@` arrives while a frame is in progress, discard the partial frame and restart from the new marker.
3. Append bytes through the line terminator without exceeding 256 bytes.
4. Complete on LF. If the preceding byte is CR, remove that CR before syntax validation. Any other CR is invalid.
5. Validate syntax, bounds, uppercase CRC text, CRC value, and message type before delivering a frame.
6. If no byte is received for 250 ms while a frame is in progress, discard the partial frame and report a timeout.

The 250 ms interval is an inter-byte timeout. An implementation using a wrapping unsigned millisecond clock should calculate elapsed time with unsigned subtraction.

## Error handling

Malformed frames, CRC failures, unsupported types, and limit violations are discarded. Receivers should expose an error to diagnostics but must not deliver a partially decoded frame. After an error, scanning resumes at the next `@`.

## Versioning

This document defines AMLP version 1. The wire frame does not carry a separate version token. Incompatible future revisions must use an out-of-band negotiation or an application profile field that both peers understand.
