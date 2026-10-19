# Smart Factory — Lab Exercises
## Beginner to Advanced

**Author:** dev-pm
**Evidence level:** L2 (simulated) unless stated; L3/L4/L5 variants marked explicitly
**Branch:** `smart-factory/t_04baa2e4-49-beginner-to-advanced-smart-factory-la`
**Base commit:** `244f333` (`docs: add hardware-blocked-issues audit for all 24 open issues`)
**Based on:** `docs/research-and-training.md`, `docs/contracts-and-data.md`, `docs/architecture/overview.md`, `docs/testing-and-acceptance.md`, `esp32-ukit-bridge/docs/mqtt-contract.md`, `esp32-ukit-bridge/shared/protocol-spec/AMLP-v1.md`

---

## Prerequisites for all labs

| Tool | Version / Source | Purpose |
|------|-----------------|---------|
| Python | >= 3.10 | Gateway, simulators, test runners |
| pnpm / Node.js | >= 18 | Dashboard, Unity host |
| MQTT broker | mosquitto 2.x or Docker | Message bus |
| Git | any recent | Source, branching |
| PlatformIO | optional | ESP32 firmware (L3+) |

**Global setup (from monorepo root):**

```bash
# Clone and enter
git clone https://github.com/vinhphan812/smart-factory.git smart-factory-labs
cd smart-factory-labs

# Python environment
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows
pip install -e ".[test]"

# MQTT broker (Docker)
docker run -d --name mqtt-broker \
  -p 1883:1883 \
  -v mosquitto.conf:/mosquitto/config/mosquitto.conf \
  eclipse-mosquitto:2

# Start broker
docker start mqtt-broker

# Verify broker
mosquitto_sub -t "smart-factory/#" -v -C 1
# (keep running; open a second terminal for publishing)
```

---

## Lab 1 — MQTT Fundamentals: Command, Status, and Telemetry

**Evidence level:** L2
**Estimated time:** 45 minutes
**Prerequisite skills:** None

### Learning objectives

By the end of this lab you will:
- Understand MQTT publish/subscribe semantics and QoS levels
- Send a JSON command payload to the correct topic
- Observe the bridge's acknowledgement response
- Distinguish between `command`, `ack`, `status`, and `telemetry` topic roles

### Setup

```bash
# Terminal 1 — subscribe to all bridge topics
mosquitto_sub -t "smart-factory/+/command/ack" -v
mosquitto_sub -t "smart-factory/+/status" -v
mosquitto_sub -t "smart-factory/+/telemetry" -v

# Terminal 2 — publish a command
mosquitto_pub -t "smart-factory/ukit-00000000/command/down" -m \
  '{"command_id":1,"command_name":"CONVEYOR_START","arguments":["60"]}'
```

### Core exercises

**Exercise 1.1 — Online status check**
Subscribe to the device status topic and observe the retained `{"status":"online"}` message. If the device is offline, the topic will be silent.

```bash
mosquitto_sub -t "smart-factory/ukit-00000000/status" -v
# Expected: {"status":"online"}
```

**Exercise 1.2 — Valid command and success ACK**
Send a `CONVEYOR_START` command. Verify the broker delivers the JSON to the bridge, which translates it to an AMLP UART frame (not observable without a serial monitor — the exercise verifies via ACK).

```bash
mosquitto_pub -t "smart-factory/ukit-00000000/command/down" -m \
  '{"command_id":1,"command_name":"CONVEYOR_START","arguments":["60"]}'
# Expected ack on smart-factory/ukit-00000000/command/ack:
# {"request_id":"1","command":"CONVEYOR_START","status":"ok","status_code":0,"attempts":1}
```

**Exercise 1.3 — Valid command with `request_id` string**
Repeat with a UUID string as correlation ID.

```bash
mosquitto_pub -t "smart-factory/ukit-00000000/command/down" -m \
  '{"request_id":"abc123","command_name":"CONVEYOR_STOP","arguments":[]}'
# Expected: ack with request_id="abc123"
```

### Expected output

| Topic | Payload |
|-------|---------|
| `smart-factory/ukit-00000000/command/ack` | `{"request_id":"1","command":"CONVEYOR_START","status":"ok","status_code":0}` |
| `smart-factory/ukit-00000000/status` | `{"status":"online"}` |

### Negative cases

| Input | Expected behaviour |
|-------|------------------|
| `command_name` not in allowlist | `status: "unknown_command"`, `status_code: 1` |
| JSON invalid | No ACK; bridge emits no response |
| `command_id` + `request_id` both present | `command_id` takes precedence |
| Empty `arguments` array | Processed; firmware uses defaults |

### Safe reset

```bash
# Stop the conveyor
mosquitto_pub -t "smart-factory/ukit-00000000/command/down" -m \
  '{"command_id":2,"command_name":"CONVEYOR_STOP","arguments":[]}'
```

### Grading rubric

| Criterion | Points |
|-----------|--------|
| Correct topic selection | 2 |
| Valid JSON command sends and ACK received | 3 |
| Both `command_id` and `request_id` formats demonstrated | 2 |
| Negative cases identified and behaviour recorded | 3 |
| **Total** | **10** |

---

## Lab 2 — AMLP Protocol: Frame Anatomy, CRC, and Deduplication

**Evidence level:** L1 (Python/C99 unit), L2 (simulator)
**Estimated time:** 60 minutes
**Prerequisite skills:** Lab 1

### Learning objectives

By the end of this lab you will:
- Parse the AMLP v1 wire format `@TYPE,fields*CRC4\r\n`
- Calculate CRC-16/CCITT-FALSE by hand and verify with the Python tool
- Understand why the UART ACK is not physical task completion
- Observe deduplication behaviour using the Python AMLP simulator

### Setup

```bash
cd esp32-ukit-bridge
python -m amlp simulate --telemetry-interval 1 &
# or:
python -m amlp simulate --commands '{"command_id":1,"command_name":"CONVEYOR_START","arguments":["60"]}'
```

### Core exercises

**Exercise 2.1 — Manual CRC calculation**

AMLP uses CRC-16/CCITT-FALSE with:
- Initial: `0xFFFF`, Polynomial: `0x1021`, No reflection, No XOR out

Calculate the CRC for the BODY `CMD,102,CONVEYOR_START,60`:

```
BODY bytes:  C M D , 1 0 2 , C O N V E Y O R _ S T A R T , 6 0
              (ASCII codes only; no @, *, or line terminator included)

CRC-16 reference (verify with Python):
>>> import crcmod
>>> crc16 = crcmod.mkCrcFun(0x1021, initCrc=0xFFFF, xorOut=0x0000, rev=False)
>>> hex(crc16(b"CMD,102,CONVEYOR_START,60"))
'0xc942'
```

Complete frame: `@CMD,102,CONVEYOR_START,60*C942\r\n`

**Exercise 2.2 — AMLP parser verification**

Use the Python test suite to confirm frame parsing handles all three types:

```bash
python -m pytest tests/python/test_protocol.py -v
```

Inspect `tests/python/test_protocol.py` and confirm it covers:
- Valid CMD/ACK/TEL frames
- CRC mismatch rejection
- Frame size > 256 bytes rejection
- Missing `@` prefix rejection
- Inter-byte timeout (250 ms gap)

**Exercise 2.3 — Deduplication with simulator**

Send the same `command_id` twice in quick succession:

```bash
# Send identical command twice
mosquitto_pub -t "smart-factory/ukit-00000000/command/down" -m \
  '{"command_id":5,"command_name":"CONVEYOR_START","arguments":["40"]}'
sleep 0.1
mosquitto_pub -t "smart-factory/ukit-00000000/command/down" -m \
  '{"command_id":5,"command_name":"CONVEYOR_START","arguments":["40"]}'
```

Observe: the second ACK should have `status: "queued"` or be rejected outright. The bridge deduplicates on `command_id` within its 16-entry cache.

**Exercise 2.4 — CRC failure injection**

Send a frame with an intentionally wrong CRC:

```bash
# Manually construct — wrong CRC
python -c "
import crcmod
crc16 = crcmod.mkCrcFun(0x1021, initCrc=0xFFFF, xorOut=0x0000, rev=False)
body = b'CMD,999,CONVEYOR_START,60'
crc = crc16(body)
wrong = crc ^ 0x0001  # flip one bit
frame = f'@CMD,999,CONVEYOR_START,60*{wrong:04X}\\r\\n'
print(repr(frame))
"
# Expected: frame discarded; no ACK emitted
```

### Expected output

```
# Exercise 2.1:
@CMD,102,CONVEYOR_START,60*C942\r\n

# Exercise 2.3:
# ACK for first: status_code 0
# ACK for second: status "queued" or rejected (implementation-dependent)
```

### Negative cases

| Input | Expected behaviour |
|-------|------------------|
| Frame without `@` prefix | Discarded; diagnostic logged |
| CRC mismatch | Discarded; no ACK |
| Frame > 256 bytes total | Rejected at parser |
| Inter-byte gap > 250 ms | Frame discarded; timeout reported |

### Safe reset

All simulator commands can be cancelled by Ctrl+C. No persistent state is written.

### Grading rubric

| Criterion | Points |
|-----------|--------|
| Correct manual CRC calculation verified | 3 |
| All three AMLP types identified in protocol docs | 2 |
| Deduplication test designed and run | 2 |
| CRC failure scenario described | 3 |
| **Total** | **10** |

---

## Lab 3 — IoT Gateway: Schema, Normalisation, and the Event Store

**Evidence level:** L2
**Estimated time:** 75 minutes
**Prerequisite skills:** Labs 1 and 2

### Learning objectives

By the end of this lab you will:
- Understand the canonical event envelope schema defined in ADR-0005
- Run the IoT gateway and observe event ingestion
- Query the event store for sequence ordering and stale-state behaviour
- Verify that the gateway never publishes commands (read-only enforcement)

### Setup

```bash
# Terminal 1 — start the MQTT broker
docker start mqtt-broker

# Terminal 2 — start the IoT gateway
cd iot-gateway
pip install -e ".[test]"
python -m uvicorn iot_gateway.main:app --host 0.0.0.0 --port 8000 &
sleep 3
curl http://localhost:8000/health
# Expected: {"status":"ok"}

# Terminal 3 — start the gateway's MQTT subscriber (gateway listens for device events)
python -m iot_gateway.mqtt_listener &
```

### Core exercises

**Exercise 3.1 — Observe canonical event envelope**

Send a command and observe the event stored by the gateway:

```bash
# Send a command
mosquitto_pub -t "smart-factory/ukit-00000000/command/down" -m \
  '{"command_id":10,"command_name":"CONVEYOR_START","arguments":["60"]}'

# Query the event store via gateway API
curl http://localhost:8000/api/v1/events?limit=5
```

Expected envelope (simplified):
```json
{
  "schema_version": "1.0.0",
  "event_id": "evt-...",
  "event_type": "device.command_completed",
  "device_id": "ukit-00000000",
  "source": "bridge",
  "occurred_at": "2026-10-17T...",
  "received_at": "2026-10-17T...",
  "sequence": 1,
  "trace_id": "...",
  "data": {
    "command": "CONVEYOR_START",
    "status": "ok",
    "status_code": 0
  }
}
```

**Exercise 3.2 — Gateway rejects command topics**

Attempt to publish to a gateway command topic (gateway must not subscribe to command topics):

```bash
# Gateway is read-only; it does not subscribe to command/down
# Verify by checking the gateway log for any subscribed topics
curl http://localhost:8000/api/v1/status
# Look for "subscribed_topics" in response
```

Expected: gateway subscribes only to `smart-factory/+/telemetry`, `smart-factory/+/status`, `smart-factory/+/command/ack`. It does **not** publish to `command/down`.

**Exercise 3.3 — Out-of-order event and sequence monotonicity**

Send two events in rapid succession and verify sequence numbers are assigned in ingestion order, not send order:

```bash
# Send event A
mosquitto_pub -t "smart-factory/ukit-00000000/telemetry" -m \
  '{"device_id":"ukit-00000000","received_at_ms":1000,"values":["CONVEYOR","RUNNING","60"]}'
sleep 0.05
# Send event B immediately after
mosquitto_pub -t "smart-factory/ukit-00000000/telemetry" -m \
  '{"device_id":"ukit-00000000","received_at_ms":900,"values":["CONVEYOR","RUNNING","55"]}'
# Note: B's received_at_ms is earlier (900 < 1000)

# Query events — verify sequence numbers are monotonically increasing
curl http://localhost:8000/api/v1/events?limit=5
# Expected: sequence increments even if device timestamps are out of order
```

**Exercise 3.4 — Stale state detection**

Stop the telemetry stream and observe stale-state indicator:

```bash
# Do NOT send any telemetry for 65 seconds (kTelemetryTimeoutMs = 60000 ms)
# After timeout:
curl http://localhost:8000/api/v1/devices/ukit-00000000/state
# Expected: {"device_id":"ukit-00000000","state":"unknown","last_seen":"2026-10-17T..."}
```

### Expected output

- Event store query returns canonical envelope with all required fields
- Gateway subscribes only to telemetry, status, and command/ack topics
- Sequence numbers are monotonically increasing in ingestion order
- Device state becomes `unknown` after telemetry timeout

### Negative cases

| Scenario | Expected behaviour |
|----------|------------------|
| Malformed JSON in telemetry | Gateway quarantines; logs error; does not crash |
| Unknown device_id | Stored with unknown device flag |
| MQTT broker disconnects | Gateway emits warning; no fabricated events |

### Safe reset

```bash
# Clear the event store (dev only)
curl -X DELETE http://localhost:8000/api/v1/events/purge

# Stop gateway
pkill -f "uvicorn iot_gateway"
```

### Grading rubric

| Criterion | Points |
|-----------|--------|
| Canonical envelope fields identified and explained | 3 |
| Out-of-order sequence test designed and verified | 3 |
| Gateway read-only behaviour verified (no command publish) | 2 |
| Stale state correctly identified after timeout | 2 |
| **Total** | **10** |

---

## Lab 4 — Factory Control Simulator: Module State Machines and Mock Adapters

**Evidence level:** L2 (simulated)
**Estimated time:** 90 minutes
**Prerequisite skills:** Labs 1–3

> **Note:** The factory-control simulator is the critical-path L2 unblock for all module adapter work (#22–#26). When the simulator is delivered (Issue #10), this lab uses its mock adapters. Until then, use the Python AMLP simulator in `esp32-ukit-bridge/tools/` to emulate device behaviour.

### Learning objectives

By the end of this lab you will:
- Understand the 9-module physical factory topology (conveyor, sorting, packaging, crane, forklift, dump truck, parking lot, bracket, combine)
- Use mock adapters to simulate a production line without physical hardware
- Observe how commands propagate through the mock module chain
- Verify that the E-stop enforcement is honoured by the simulator

### Setup

```bash
# Start MQTT broker (if not running)
docker start mqtt-broker

# Start the Python AMLP simulator as a mock device
cd esp32-ukit-bridge
python -m amlp simulate --mode conveyor --telemetry-interval 2 &
SIM_PID=$!
echo "Simulator PID: $SIM_PID"
```

### Core exercises

**Exercise 4.1 — Single module: start/stop conveyor**

```bash
# Start conveyor at speed 60
mosquitto_pub -t "smart-factory/ukit-00000000/command/down" -m \
  '{"command_id":100,"command_name":"CONVEYOR_START","arguments":["60"]}'

# Observe telemetry stream
mosquitto_sub -t "smart-factory/ukit-00000000/telemetry" -v -C 3
# Expected: {"device_id":"ukit-00000000","received_at_ms":...,"values":["CONVEYOR","RUNNING","60"]}

# Stop conveyor
mosquitto_pub -t "smart-factory/ukit-00000000/command/down" -m \
  '{"command_id":101,"command_name":"CONVEYOR_STOP","arguments":[]}'

mosquitto_sub -t "smart-factory/ukit-00000000/telemetry" -v -C 1
# Expected: RUNNING → STOPPED
```

**Exercise 4.2 — Simulated sorting module routing**

> Sorting module adapter (#23) is blocked at L3. Mock it with a Python script that emits telemetry with different `SORT_OUTPUT` values.

```python
# mock_sorting.py (simplified)
import paho.mqtt.client as mqtt
import json, time

client = mqtt.Client()
client.connect("localhost", 1883, 60)

for i, output in enumerate(["A", "B", "C"]):
    payload = {
        "device_id": "sorting-01",
        "received_at_ms": int(time.time() * 1000),
        "values": ["SORTING", f"OUTPUT_{output}", "PASS"],
        "pairs": {"item_id": str(i), "output": output}
    }
    client.publish("smart-factory/sorting-01/telemetry", json.dumps(payload))
    time.sleep(1)
```

Run: `python mock_sorting.py`

**Exercise 4.3 — Module chain: conveyor → sorting → packaging (simulated)**

Orchestrate a three-step production sequence:

```bash
# Step 1: Start conveyor
mosquitto_pub -t "smart-factory/conveyor-01/command/down" -m \
  '{"command_id":200,"command_name":"CONVEYOR_START","arguments":["60"]}'

# Step 2: After 5s, trigger sorting decision (mock)
sleep 5
python mock_sorting.py

# Step 3: Trigger packaging (mock)
sleep 3
python -c "
import paho.mqtt.client as mqtt, json, time
c = mqtt.Client()
c.connect('localhost', 1883, 60)
c.publish('smart-factory/packaging-01/telemetry', json.dumps({
    'device_id': 'packaging-01',
    'received_at_ms': int(time.time()*1000),
    'values': ['PACKAGING', 'COMPLETE'],
    'pairs': {'items_packed': '1'}
}))
"
```

**Exercise 4.4 — E-stop enforcement**

Test that the simulator honours a simulated emergency stop command (firmware enforces E-stop locally — verify the expected behaviour):

```bash
# In production, E-stop is a physical signal or a special MQTT topic
# For L2 simulation, verify the state machine rejects commands after E-stop flag:
curl http://localhost:8000/api/v1/devices/ukit-00000000/estop
# Expected: {"estop_active": false}

# Note: real E-stop enforcement requires L4 hardware
# This exercise verifies the state machine contract, not physical safety
```

### Expected output

- Conveyor telemetry shows `RUNNING` then `STOPPED` states
- Sorting telemetry shows `OUTPUT_A/B/C` routing decisions
- Packaging telemetry shows `COMPLETE` after item arrives
- E-stop flag is observable via API

### Negative cases

| Scenario | Expected behaviour |
|----------|------------------|
| Speed > 100 in CONVEYOR_START | `status: invalid_argument` |
| Unknown command name | `status: unknown_command` |
| Command sent while E-stop active | Command rejected; `status: internal_error` |

### Safe reset

```bash
kill $SIM_PID
mosquitto_pub -t "smart-factory/ukit-00000000/command/down" -m \
  '{"command_id":999,"command_name":"CONVEYOR_STOP","arguments":[]}'
```

### Grading rubric

| Criterion | Points |
|-----------|--------|
| Single module start/stop verified end-to-end | 2 |
| Sorting routing mock designed and executed | 3 |
| Three-module chain demonstrated | 3 |
| E-stop contract verified (state machine only, not physical) | 2 |
| **Total** | **10** |

---

## Lab 5 — Unity 3D Digital Twin: Event Replay and Stale Indicators

**Evidence level:** L2 (event replay); L3/L4 blocked on hardware
**Estimated time:** 60 minutes
**Prerequisite skills:** Labs 1–4

> **Note:** Unity scaffold (#11) is independently unblocked at L2. This lab assumes `digital-twin/` contains Unity project stubs and a mock event adapter. Without the scaffold, use the `integration-tests/` mock to demonstrate the event-replay concept.

### Learning objectives

By the end of this lab you will:
- Understand how the Digital Twin subscribes to the gateway's WebSocket broadcast
- Observe Twin state updates responding to simulated events
- Verify that the Twin shows `unknown/stale` when telemetry is absent
- Record and replay a production sequence from the event store

### Setup

```bash
# Terminal 1 — gateway with WebSocket broadcast enabled
cd iot-gateway
python -m uvicorn iot_gateway.main:app --host 0.0.0.0 --port 8000 &

# Terminal 2 — mock Twin client (WebSocket subscriber)
# The mock Twin is in integration-tests/ or digital-twin/tests/mock_twin_client.py
python -m integration_tests.mock_twin_client &
```

### Core exercises

**Exercise 5.1 — Normal production state**

Send a sequence of events and observe Twin state:

```bash
# Start conveyor
mosquitto_pub -t "smart-factory/conveyor-01/command/down" -m \
  '{"command_id":300,"command_name":"CONVEYOR_START","arguments":["60"]}'

# Check mock Twin state
curl http://localhost:8001/api/v1/twin/state  # mock Twin API port 8001
# Expected: {"conveyor-01": {"state": "RUNNING", "speed": 60, "last_update": "..."}}
```

**Exercise 5.2 — Stale/offline indicator**

Wait 65 seconds, then check Twin state:

```bash
sleep 65
curl http://localhost:8001/api/v1/twin/state
# Expected: {"conveyor-01": {"state": "unknown", "stale": true}}
```

The Twin must show `unknown/stale`, **not** infer a running state from lack of telemetry.

**Exercise 5.3 — Event replay**

Query the event store for the last 10 events and replay them to the Twin:

```bash
# Fetch events
curl http://localhost:8000/api/v1/events?limit=10 > replay_events.json

# Replay via mock Twin
python -m integration_tests.replay_events replay_events.json

# Verify Twin reflects the same sequence
curl http://localhost:8001/api/v1/twin/state | jq .
```

**Exercise 5.4 — Out-of-order event monotonicity (E07)**

Inject an old telemetry message (earlier timestamp) and verify Twin does not roll backward:

```bash
# Send "old" telemetry with a timestamp in the past
mosquitto_pub -t "smart-factory/conveyor-01/telemetry" -m \
  '{"device_id":"conveyor-01","received_at_ms":1000000,"values":["CONVEYOR","RUNNING","30"]}'

curl http://localhost:8001/api/v1/twin/state
# Expected: speed remains at 60 (most recent value); Twin does NOT roll backward
```

### Expected output

| Event | Twin state |
|-------|-----------|
| CONVEYOR_START speed=60 | `RUNNING, speed=60` |
| No telemetry for 65 s | `unknown, stale=true` |
| Old out-of-order telemetry | State unchanged (monotonic) |

### Negative cases

| Scenario | Expected behaviour |
|----------|------------------|
| Twin receives malformed event JSON | Event dropped; no crash; logged |
| Twin disconnects and reconnects | Full snapshot replay from event store |

### Safe reset

```bash
pkill -f "mock_twin_client"
curl -X DELETE http://localhost:8000/api/v1/events/purge
```

### Grading rubric

| Criterion | Points |
|-----------|--------|
| Normal state update correctly reflected in Twin | 2 |
| Stale/online indicator shown after timeout | 3 |
| Event replay produces correct Twin state | 3 |
| Out-of-order events do not cause rollback | 2 |
| **Total** | **10** |

---

## Lab 6 — Edge AI Anomaly Detection: Rule-Based Alarm Taxonomy

**Evidence level:** L2 (mock fixtures); L5 blocked on physical MiniAlpha
**Estimated time:** 75 minutes
**Prerequisite skills:** Labs 1–5

### Learning objectives

By the end of this lab you will:
- Understand the deterministic alarm taxonomy defined in Issue #14
- Design rule-based anomaly detection using scripted fixtures
- Measure false-positive and false-negative rates on synthetic data
- Observe how the robot adapter handles an unsupported-skill notification

### Setup

```bash
cd edge-ai-robot
pip install -e ".[test]"
python -m pytest tests/ -v --tb=short
```

### Core exercises

**Exercise 6.1 — Alarm taxonomy mapping**

Define alarm severity levels using the taxonomy:

| Alarm ID | Severity | Rule |
|----------|----------|------|
| `ALM-01` | CRITICAL | Conveyor jam: no movement for >30 s while RUNNING |
| `ALM-02` | HIGH | Sorting timeout: no output detected for >60 s |
| `ALM-03` | MEDIUM | Speed deviation: speed changed >20% without command |
| `ALM-04` | LOW | Telemetry gap: stale indicator >60 s |
| `ALM-05` | CRITICAL | E-stop activated |

**Exercise 6.2 — Scripted fixture: conveyor jam**

```python
# test_jam_detection.py
import pytest, time
from edge_ai_robot.alarm import AlarmDetector

def test_conveyor_jam_detected():
    detector = AlarmDetector()

    # Simulate RUNNING state
    detector.update("conveyor-01", {"state": "RUNNING", "speed": 60}, timestamp=time.time())
    
    # Wait 35 seconds without state change
    time.sleep(35)

    # Simulate no state change (still RUNNING at 35s mark)
    result = detector.update("conveyor-01", {"state": "RUNNING", "speed": 60}, timestamp=time.time() + 35)
    
    assert "ALM-01" in [a.id for a in result.alarms]
    assert result.severity == "CRITICAL"
```

Run: `python -m pytest tests/test_jam_detection.py -v`

**Exercise 6.3 — False-positive measurement**

Measure false positives on a normal production run (no alarms expected):

```python
def test_normal_run_no_false_positives():
    detector = AlarmDetector()
    alarms = []
    for t in range(0, 300, 5):  # 5-minute normal run
        state = {"state": "RUNNING", "speed": 60}
        result = detector.update("conveyor-01", state, timestamp=t)
        alarms.extend(result.alarms)
    
    critical_alarms = [a for a in alarms if a.severity == "CRITICAL"]
    assert len(critical_alarms) == 0, f"False positives: {critical_alarms}"
```

**Exercise 6.4 — Unsupported-skill robot response**

Test that the robot adapter correctly rejects an unsupported skill request:

```bash
# With mock robot adapter running:
python -m edge_ai_robot.mock_adapter

# Send unsupported skill:
curl -X POST http://localhost:8002/api/v1/skill \
  -H "Content-Type: application/json" \
  -d '{"skill": "RESCUE_CONVEYOR", "device": "conveyor-01"}'
# Expected: {"status": "unsupported", "reason": "Skill not in allowed list"}
```

### Expected output

```
test_jam_detection.py::test_conveyor_jam_detected PASSED
  ALM-01 CRITICAL: Conveyor jam detected on conveyor-01
test_normal_run_no_false_positives PASSED
  0 critical alarms in 300s normal run
```

### Negative cases

| Scenario | Expected behaviour |
|----------|------------------|
| Alarm triggered then cleared | ALM-01 resolved; event recorded |
| Multiple concurrent alarms | All tracked; highest severity escalated |
| Robot unreachable during alarm | Alarm stored; robot notified on reconnect |

### Safe reset

```bash
pkill -f "mock_adapter"
```

### Grading rubric

| Criterion | Points |
|-----------|--------|
| Alarm taxonomy documented with severity levels | 2 |
| Jam detection test designed and passing | 3 |
| False-positive rate measured (0% for normal run) | 2 |
| Unsupported skill rejection verified | 3 |
| **Total** | **10** |

---

## Lab 7 — End-to-End Integration: Command → ACK → Event → Twin

**Evidence level:** L2 (simulated); L5 blocked on physical hardware
**Estimated time:** 90 minutes
**Prerequisite skills:** Labs 1–6

### Learning objectives

By the end of this lab you will:
- Trace a complete command through the full software stack: MQTT command → bridge ACK → gateway event → Twin state
- Measure round-trip latency at each hop
- Verify that no unsafe command executes after broker disconnect
- Tag each verification step as L2 (simulated) or blocked L5

### Setup

```bash
# Full stack (all components running)
docker start mqtt-broker
cd iot-gateway && python -m uvicorn iot_gateway.main:app --port 8000 &
sleep 2
python -m integration_tests.mock_twin_client &
sleep 1
cd esp32-ukit-bridge && python -m amlp simulate --mode conveyor &
```

### Core exercises

**Exercise 7.1 — Complete trace: CONVEYOR_START**

Send a command and observe every hop:

```bash
# Terminal 1: Monitor all topics
mosquitto_sub -t "smart-factory/+/command/down" -v &
mosquitto_sub -t "smart-factory/+/command/ack" -v &
mosquitto_sub -t "smart-factory/+/telemetry" -v &

# Terminal 2: Send command
START=$(date +%s%3N)
mosquitto_pub -t "smart-factory/conveyor-01/command/down" -m \
  '{"command_id":400,"command_name":"CONVEYOR_START","arguments":["60"]}'
```

Collect the following timestamps:

| Hop | Timestamp | Observable |
|-----|-----------|------------|
| Command published | T0 | `mosquitto_pub` output |
| Bridge ACK received | T1 | `smart-factory/conveyor-01/command/ack` |
| Gateway event stored | T2 | `iot-gateway/api/v1/events` |
| Twin state updated | T3 | `mock_twin_client` log |

Round-trip software latency = T3 - T0

**Exercise 7.2 — Duplicate command (E03)**

Send the same `command_id` twice:

```bash
mosquitto_pub -t "smart-factory/conveyor-01/command/down" -m \
  '{"command_id":401,"command_name":"CONVEYOR_START","arguments":["60"]}'
sleep 0.5
mosquitto_pub -t "smart-factory/conveyor-01/command/down" -m \
  '{"command_id":401,"command_name":"CONVEYOR_START","arguments":["60"]}'
# Expected: first ACK "ok"; second ACK "queued" or rejected
# Verify: no duplicate physical actuation logged
```

**Exercise 7.3 — Invalid command (E02)**

Send a malformed payload:

```bash
mosquitto_pub -t "smart-factory/conveyor-01/command/down" -m \
  '{"command_id":402,"command_name":"CONVEYOR_FLY","arguments":["100"]}'
# Expected: bridge ACK with status "unknown_command"; no UART frame sent
```

**Exercise 7.4 — Broker disconnect safety (E06)**

```bash
# While conveyor is running:
mosquitto_pub -t "smart-factory/conveyor-01/command/down" -m \
  '{"command_id":403,"command_name":"CONVEYOR_START","arguments":["60"]}'

# Disconnect broker
docker stop mqtt-broker

# Wait 10 seconds
sleep 10

# Verify Twin shows stale, not running
curl http://localhost:8001/api/v1/twin/state
# Expected: {"conveyor-01": {"state": "unknown", "stale": true}}
# Critical: no command queued for unsafe execution after disconnect

# Reconnect broker
docker start mqtt-broker
```

### Expected output

| Test | L2 result | L5 status |
|------|-----------|-----------|
| Complete trace | All hops observable | **BLOCKED** (physical controller) |
| Duplicate command | Rejected; no duplicate actuation | **BLOCKED** (physical controller) |
| Invalid command | Rejected at bridge | **BLOCKED** (physical controller) |
| Broker disconnect | Twin → stale; no unsafe execution | **BLOCKED** (physical E-stop) |

### Safe reset

```bash
docker start mqtt-broker
mosquitto_pub -t "smart-factory/conveyor-01/command/down" -m \
  '{"command_id":999,"command_name":"CONVEYOR_STOP","arguments":[]}'
```

### Grading rubric

| Criterion | Points |
|-----------|--------|
| Complete 4-hop trace documented with timestamps | 3 |
| Duplicate rejection correctly predicted and verified | 2 |
| Invalid command rejection documented | 2 |
| Disconnect behaviour documented (stale, no unsafe exec) | 3 |
| **Total** | **10** |

---

## Lab 8 — Research Quality: KPIs, Run Manifests, and Evidence Packaging

**Evidence level:** L2 (simulated)
**Estimated time:** 60 minutes
**Prerequisite skills:** Labs 1–7

### Learning objectives

By the end of this lab you will:
- Capture scientific KPIs: sync latency, message loss, duplicate rate
- Produce a run manifest with commit SHA, firmware version, and environment
- Package evidence for reproducibility
- Understand the distinction between L2 (simulator) and L5 (physical) evidence

### Core exercises

**Exercise 8.1 — Latency measurement**

Use the gateway's built-in latency capture:

```bash
# Capture 300-second run
cd scripts
python capture_latency.py \
  --run-id "lab8-run-001" \
  --duration 300 \
  --level L2 \
  --broker "mosquitto:2.0.18" \
  --output run_001_manifest.yaml
```

Inspect the output manifest:

```yaml
run_id: "lab8-run-001"
commit: "244f333"
firmware_version: "simulator-v0.1.0"
start_iso: "2026-10-17T..."
end_iso: "2026-10-17T..."
level: "L2"
broker: "mosquitto:2.0.18"
gateway: "Python 3.10 / commit ..."
results:
  latency_p50_ms: <float>
  latency_p95_ms: <float>
  latency_p99_ms: <float>
  latency_max_ms: <float>
  loss_rate: <float>
  duplicate_rate: <float>
  reconnect_time_ms: null
  msg_sent: <int>
  msg_stored: <int>
criteria_pass: true  # reviewer sets after review
notes: "L2 simulator run; no physical hardware involved"
```

**Exercise 8.2 — Evidence packaging**

Package the run as a reproducibility bundle:

```
smart-factory-evidence/
├── run_manifest.yaml          # mandatory
├── gateway_logs/              # gateway startup to shutdown
├── event_store_dump.json      # SQLite export
├── twin_state_snapshots/      # Twin state at start, mid, end
├── broker_config/             # mosquitto.conf used
└── README.md                  # how to reproduce
```

**Exercise 8.3 — L2 vs L5 evidence gap analysis**

For each KPI, document what changes when you move from L2 to L5:

| KPI | L2 (simulator) | L5 (physical) | Evidence needed |
|-----|---------------|--------------|-----------------|
| `latency_p50_ms` | ~5–50 ms (local loopback) | **BLOCKED** — depends on physical UART round-trip | Real ESP32 + controller wiring |
| `loss_rate` | 0% (local broker) | **BLOCKED** — Wi-Fi packet loss possible | Real ESP32 on bench |
| `duplicate_rate` | 0% (deterministic) | **BLOCKED** — retry race conditions | Physical retry tests |
| `reconnect_time_ms` | Broker reconnect | **BLOCKED** — Wi-Fi failover | Real ESP32 on bench |

> **Important:** Do not claim L5 results from an L2 run. Every KPI table must clearly label which rows are simulated vs measured.

### Expected output

- A `run_manifest.yaml` with real measured values (no invented numbers)
- An evidence bundle structured as above
- A gap analysis distinguishing L2 from L5 evidence requirements

### Grading rubric

| Criterion | Points |
|-----------|--------|
| Latency capture script designed and run | 3 |
| Run manifest contains all required fields | 2 |
| Evidence bundle structure correct | 2 |
| L2/L5 gap analysis accurately identifies blockers | 3 |
| **Total** | **10** |

---

## Lab 9 — Safety and E-Stop: Physical Safety Constraints (L4/L5)

**Evidence level:** L4 / L5 (BLOCKED — requires physical hardware)
**Estimated time:** 120 minutes (when hardware available)

> **Warning:** This lab requires the full 9-module physical subsystem with verified electrical wiring, grounding, E-stop button, and an operator present. Do NOT attempt any physical actuation without completing the hardware pre-check in `docs/testing-and-acceptance.md`.

### When this lab is unblocked

Follow the hardware pre-check checklist before beginning:

- [ ] Voltage levels verified with multimeter (all module controllers at safe voltage)
- [ ] Grounding confirmed for ESP32, UKIT controllers, and power supply
- [ ] E-stop button physically tested — confirms all motion stops immediately
- [ ] Operator briefed on emergency procedures
- [ ] Workspace clear of obstructions
- [ ] Wiring diagram approved by lab supervisor

### Learning objectives

By the end of this lab you will:
- Trigger E-stop and observe immediate motion cessation across all modules
- Verify that no command executes for 60 seconds after E-stop activation
- Measure E-stop response time (command to full stop)
- Document voltage measurements at key nodes

### Core exercises (L4)

**Exercise 9.1 — E-stop response time measurement**

```bash
# All modules running at normal speed
# Operator activates E-stop button
# Measure time from button press to all motion stopped
# Record: E-stop response time = <measured_ms> ms
# Pass criterion: < 200 ms
```

**Exercise 9.2 — Post E-stop command rejection**

```bash
# After E-stop activated, attempt command:
mosquitto_pub -t "smart-factory/conveyor-01/command/down" -m \
  '{"command_id":999,"command_name":"CONVEYOR_START","arguments":["60"]}'

# Expected: no motion; command rejected at adapter layer
# Record: command rejected by E-stop guard
```

### Evidence required (L4)

| Evidence | Requirement |
|----------|------------|
| Voltage measurements | Multimeter readings at each controller |
| E-stop response time | Stopwatch measurement |
| Wiring diagram | Approved CAD or photo |
| Operator sign-off | Lab supervisor signature |

### Grading rubric (L4)

| Criterion | Points |
|-----------|--------|
| Hardware pre-check completed and signed | 2 |
| E-stop response time < 200 ms | 3 |
| Post-E-stop command correctly rejected | 3 |
| Voltage measurements documented | 2 |
| **Total** | **10** |

---

## Evidence Level Summary

| Lab | L0 | L1 | L2 | L3 | L4 | L5 |
|-----|----|----|----|----|----|----|
| 1 — MQTT fundamentals | | | ✅ | | | |
| 2 — AMLP protocol | | ✅ | ✅ | | | |
| 3 — IoT gateway | | | ✅ | | | |
| 4 — Factory simulator | | | ✅ | **BLOCKED** | **BLOCKED** | |
| 5 — Unity Digital Twin | | | ✅ | **BLOCKED** | **BLOCKED** | **BLOCKED** |
| 6 — AI anomaly detection | | | ✅ | | | **BLOCKED** |
| 7 — E2E integration | | | ✅ | **BLOCKED** | **BLOCKED** | **BLOCKED** |
| 8 — Research KPIs | | | ✅ | | | |
| 9 — Safety / E-stop | | | | | **BLOCKED** | **BLOCKED** |

**Legend:**
- ✅ = Deliverable at this level (no hardware dependency)
- **BLOCKED** = Requires hardware procurement, bench setup, or L5 integration

---

## Blocked Labs Reference

| Lab | Blocker | Required action | Owner |
|-----|---------|----------------|-------|
| 4 physical adapters | #9 (9-module procurement) | Procure + inventory all 9 modules | dev-pm |
| 5 Unity Twin | #11 (Unity scaffold) + #12 (event adapter) | Build scaffold + event adapter | dev-backend |
| 6 physical robot | #13 (MiniAlpha connectivity) | Confirm MiniAlpha unit availability | dev-pm |
| 7 physical chain | All module adapters + Twin | Complete L2 first | dev-backend |
| 9 E-stop | #9 + verified wiring | Complete hardware procurement + wiring | dev-pm |

---

## Lab Difficulty Progression

```
BEGINNER (Labs 1–2)
  └─ MQTT pub/sub + AMLP wire format + CRC
     No code, pure protocol understanding

INTERMEDIATE (Labs 3–4)
  ├─ Gateway + event schema + normalisation
  └─ Factory module state machines (mock adapters)

ADVANCED (Labs 5–7)
  ├─ Unity Digital Twin (event replay, stale indicators)
  ├─ AI anomaly detection (rule taxonomy, false-positive rates)
  └─ E2E integration (full trace, fault injection)

EXPERT (Labs 8–9)
  ├─ Scientific KPIs + run manifests + evidence packaging
  └─ Physical safety verification (L4, hardware required)
```

---

## Glossary

| Term | Definition |
|------|-----------|
| AMLP | ASCII Machine Link Protocol v1 — UART framing with CRC-16 |
| Bridge | ESP32-S3 MQTT-to-AMLP UART adapter |
| Canonical envelope | Standard JSON event schema defined in ADR-0005 |
| E-stop | Emergency stop — hardware safety interrupt |
| HIL | Hardware-in-the-Loop — real hardware with simulated control |
| IoT Gateway | Normalises and stores device events; does not issue commands |
| L0–L5 | Evidence levels from static review (L0) to integrated factory (L5) |
| Stale state | Twin/Dashboard indication when no telemetry received for 60 s |
| Twin | Unity 3D Digital Twin — reflects observed factory state |
