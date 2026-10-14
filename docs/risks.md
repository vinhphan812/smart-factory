# Risks, mitigations and open dependencies

| Risk | Impact | Mitigation / proof | Issues |
|---|---|---|---|
| No verified UKIT SDK, pinout or 3.3 V compatibility | Hardware damage or blocked firmware deployment | Vendor manual, voltage verification, interface adapter and HIL | #4 #20 |
| 9 physical modules pending procurement/interface mapping | No complete line | Capability inventory and simulation fallback, no fake HIL PASS | #9 #42 |
| Bridge UART TEL not yet MQTT | Twin cannot be real-time | Implement telemetry path + tested gateway + stale semantics | #7 #12 #29 |
| AI or UI bypasses local interlocks | Unsafe motion | Fail-closed policy, device bounds, local E-stop | #5 #37 #40 |
| MiniAlpha hardware/software API unknown | Robot demo unavailable | Capability matrix, mocks and vendor-supported tests | #13 #36 |
| Unity scene/model asset size and licensing uncertain | Bad Git performance / legal exposure | Pin engine, Git LFS, asset-license review | #11 #33 |
| Duplicates, stale messages, clock skew | Incorrect twin or repeated command | sequence/version, expiry, idempotency, snapshot | #3 #30 #34 |
| Sensitive keys or vendor SDK committed to public repo | Security/IP disclosure | secret scanning, placeholder env, legal review | #19 #41 |
| Simulation results mistaken for physical results | Invalid research reports | Explicit test evidence levels + reproducibility | #18 #46 #48 |
| Backlog without ownership | Execution slips | Issue claim, owner, dependencies, periodic triage | #19 #52 |

Log each risk's owner, status, evidence link and next review in Issues. Escalate a credible physical safety defect as P0 and suspend affected real actuation until tested and approved.
