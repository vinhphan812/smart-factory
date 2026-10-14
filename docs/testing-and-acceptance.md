# Testing and acceptance — Smart Factory

## Test evidence levels
| Level | Environment | What it proves |
|---|---|---|
| L0 | static/schema | shape and review only |
| L1 | Python/C99/C++ host unit | local algorithms and parsers |
| L2 | simulated UART/MQTT, mock device | software protocol/application behavior |
| L3 | ESP32 connected to real controller (bench) | verified electrical and link interoperability |
| L4 | actual moving 9-module subsystem, operator/E-stop | physical safety and actuation |
| L5 | integrated factory→gateway→Unity→MiniAlpha | stated end-to-end scenarios with declared mock/real mix |

## End-to-end acceptance scenarios
| ID | Stimulus | Expected result |
|---|---|---|
| E01 | Normal production | Correlated transport, sort, pack and store completion trace |
| E02 | Invalid command payload | Error; no physical action |
| E03 | Duplicate correlation ID | Device action not re-executed |
| E04 | Bad CRC/oversize AMLP | Rejection and diagnostic |
| E05 | Jam / sensor timeout | Local safety stop and incident |
| E06 | Broker disconnect | Stale indication; no unsafe queued execution |
| E07 | Out-of-order event | Twin state does not roll backward |
| E08 | Reconnect | Snapshot resync; expired commands rejected |
| E09 | MiniAlpha offline/unsupported skill | Explicit failure; no actuation |
| E10 | AI unsafe action request | Policy gate rejects; audit present |
| E11 | Emergency stop | Works locally even without MQTT |
| E12 | Event replay | Reproducible recorded state and trace |

## Scientific KPIs
Sync delay p50/p95/p99, message loss/duplicates, recovery time, anomalous-event accuracy/false alarms, robot alert/response, production cycle reliability. Measure and publish raw observations with run manifest, timestamp strategy, commit, firmware version, simulator-vs-hardware level and repetitions. **Do not invent thresholds or claim PASS without evidence.**

## Issue Definition of Done
- [ ] Scope implemented and linked PR reviewed.
- [ ] Tests from issue executed and evidence attached.
- [ ] Negative paths, safety and disconnect behavior checked.
- [ ] Schema and documentation updated.
- [ ] Hardware tests, when required, include verified voltage, grounding, controlled workspace, operator and E-stop precheck.
- [ ] Blocked hardware requirements clearly remain BLOCKED, not skipped as PASS.
