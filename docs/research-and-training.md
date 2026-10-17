# Research and teaching use cases

## Scientific evaluation
The engineering work packages are architecture, physical logistics integration, real-time data collection/synchronization, **Unity 3D Digital Twin**, and UBTECH Yanshee AI Edge response. The original research proposal used the term Unreal Engine; the administrative approval status of this technology change is not verified. Expected evidence includes:
- production cycle state traces with recorded sensor/controller states;
- MQTT/AMLP round-trip and malformed/duplicate case coverage;
- gateway→Twin latency p50/p95/p99, event loss, clock assumptions, stale-state recovery;
- robot bounded alert response, unsupported capabilities and cancellations;
- incident/anomaly datasets, false positive/negative counts and safe-stop outcome;
- reproducible run manifest (code SHA, firmware, dataset, test setup and simulated/physical environment).

## Planned lab exercises
| Lab | Topic | Mode |
|---|---|---|
| L1 | MQTT command, status and telemetry concepts | Simulator |
| L2 | AMLP frame, CRC and deduplication | Python/C99 tests |
| L3 | Safe conveyor/sorting controller | Mock initially |
| L4 | IoT gateway schema and registry | Synthetic messages |
| L5 | Unity 3D factory state + stale indicators | Event replay |
| L6 | AI anomaly triage and measured errors | Labeled datasets |
| L7 | UBTECH Yanshee skill request, terminal feedback | Mock then HIL |
| L8 | E2E reliability and safe-stop experiment | Bench/HIL after approval |

Labs beyond the existing bridge are **planned**, not currently delivered. For each lab provide learning objectives, setup, expected output, negative cases, safe reset and grading rubric. Technical demos should explain which actions are simulated.
