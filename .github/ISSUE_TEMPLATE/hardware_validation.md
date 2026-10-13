---
name: Hardware Validation
description: Document physical hardware bring-up, integration or testing
labels: [hardware, validation]
title: "[HARDWARE] "
---

## Hardware Under Test

| Item | Model / Version | Serial (if known) |
|---|---|---|
| ESP32-S3 | | |
| Arduino MEGA 2560 | | |
| uKit Explore | | |
| MX0508 level shifter | | |
| Logic analyzer | | |
| MQTT broker | | |

## Test Environment

- Location:
- Network (lab isolated / production LAN):
- Safety equipment available:

## Safety Checklist

- [ ] E-stop within reach
- [ ] Voltage levels verified with multimeter before power-on
- [ ] UART wiring double-checked (GND common, TX→RX cross)
- [ ] MEGA TX0 → ESP32 RX has level shifter (3.3 V max)
- [ ] No actuator power until bench review complete

## Test Cases

| TC | Description | Pass | Evidence |
|---|---|---|---|
| TC1 | | ☐ | |
| TC2 | | ☐ | |

## Evidence

- [ ] Photos of wiring
- [ ] Logic analyzer captures
- [ ] Serial output logs
- [ ] Video recording

## Findings

<!-- What worked? What did not? What is still blocked? -->

## Sign-off

- [ ] Bench review completed
- [ ] Known blockers documented as issues
- [ ] Results linked to relevant issues

## Notes

<!-- Any unexpected behavior, environmental conditions, or observations -->
