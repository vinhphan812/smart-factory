"""WebSocket and HTTP API servers for the gateway."""

import asyncio
import json
import logging
import os
import secrets
from typing import Any

import websockets
from fastapi import Depends, FastAPI, HTTPException, Query, Header
from pydantic import BaseModel

from .event_store import EventStore
from .time_sync import TimeMetrics
from .safety_gate import SafetyGate

logger = logging.getLogger(__name__)

#: X-Operator-Token value from environment. Empty string if not configured.
OPERATOR_TOKEN = os.environ.get("SAFETY_OPERATOR_TOKEN", "")


def _require_operator_token(x_operator_token: str = Header(None)) -> str:
    """Validate X-Operator-Token against SAFETY_OPERATOR_TOKEN.

    Raises HTTP 401 if the header is missing, empty, or does not match
    SAFETY_OPERATOR_TOKEN (checked with secrets.compare_digest to mitigate
    timing attacks).

    Returns the validated token string.
    """
    if not OPERATOR_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Operator authentication is not configured on this server.",
        )
    if not x_operator_token:
        raise HTTPException(
            status_code=401,
            detail="X-Operator-Token header is required.",
        )
    if not secrets.compare_digest(x_operator_token, OPERATOR_TOKEN):
        raise HTTPException(
            status_code=401,
            detail="Invalid operator token.",
        )
    return x_operator_token


class EventQuery(BaseModel):
    device_id: str | None = None
    event_type: str | None = None
    limit: int = 100


class WebSocketServer:
    """Broadcasts events to all connected WebSocket clients.

    Each client has its own outbound queue so that slow clients do not block
    fast clients and every connected client receives every broadcast event.

    Uses the ``websockets`` library (RFC-6455) so Unity, browsers, and any
    standards-compliant WebSocket client can connect.

    Args:
        host: Bind address.
        port: Bind port.
        store: Optional EventStore for snapshot queries.
        metrics: Optional TimeMetrics for observability.
    """

    MAX_QUEUE_PER_CLIENT = 64

    def __init__(self, host: str, port: int, store: EventStore | None = None, metrics: TimeMetrics | None = None) -> None:
        self._host = host
        self._port = port
        self._store = store
        self._metrics = metrics
        # Per-client queue set — each client task pulls from its own queue
        self._client_queues: set[asyncio.Queue[str]] = set()
        self._queues_lock: asyncio.Lock = asyncio.Lock()
        self._server: websockets.Server | None = None

    async def start(self) -> None:
        """Start the WebSocket server on self._host:self._port."""
        # Define the handler as a lambda so websockets.serve receives a regular
        # callable, not a bound method whose return value (coroutine) might not
        # be awaited correctly on all Python/asyncio versions.
        async def handler(conn: websockets.ServerConnection) -> None:
            client_queue: asyncio.Queue[str] = asyncio.Queue(
                maxsize=self.MAX_QUEUE_PER_CLIENT
            )

            async with self._queues_lock:
                self._client_queues.add(client_queue)
            addr = conn.remote_address
            logger.info("WS client connected: %s", addr)
            try:
                while True:
                    # Wait for the next message with a timeout.  On timeout,
                    # check whether the connection has been closed so we exit
                    # promptly when the client departs.
                    try:
                        data = await asyncio.wait_for(
                            client_queue.get(), timeout=1.0
                        )
                    except asyncio.TimeoutError:
                        if conn.close_code is not None:
                            # Connection closed — exit so the finally block
                            # unregisters the queue.
                            break
                        # Still connected; yield to the event loop and loop
                        # back to wait on the queue again.
                        continue
                    await conn.send(data)
            except websockets.exceptions.ConnectionClosed:
                pass
            finally:
                async with self._queues_lock:
                    self._client_queues.discard(client_queue)
                logger.info("WS client disconnected: %s", addr)

        self._server = await websockets.serve(
            handler,
            self._host,
            self._port,
        )
        logger.info("WebSocket server started on %s:%d", self._host, self._port)

    async def broadcast(self, event_dict: dict[str, Any]) -> None:
        """Fan-out an event to every connected client.

        Serializes the event once and enqueues the string in each client's
        individual queue. Uses put_nowait so a full client queue does not block
        the calling write worker — the lagging client is disconnected instead.
        """
        payload = json.dumps(event_dict, default=str)
        async with self._queues_lock:
            queues = list(self._client_queues)
        if not queues:
            return

        lagging: list[asyncio.Queue[str]] = []
        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                lagging.append(q)

        if lagging:
            async with self._queues_lock:
                for q in lagging:
                    self._client_queues.discard(q)
            logger.warning(
                "Dropped %d lagging WebSocket client(s) — outbound queue full "
                "(maxsize=%d)",
                len(lagging),
                self.MAX_QUEUE_PER_CLIENT,
            )

    async def shutdown(self) -> None:
        """Close the WebSocket server gracefully."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()


def create_http_app(
    store: EventStore,
    metrics: TimeMetrics | None = None,
    dropped_count_ref: dict[str, int] | None = None,
    safety_gate: SafetyGate | None = None,
) -> FastAPI:
    """Build FastAPI app with REST endpoints backed by the event store.

    Args:
        store: EventStore instance for event persistence.
        metrics: Optional TimeMetrics for latency/staleness observability.
        dropped_count_ref: Optional shared dict with key "dropped" holding the
            gateway's cumulative queue-dropped counter. The /health endpoint
            reads it to report overflow to callers.
        safety_gate: Optional SafetyGate instance for command safety evaluation.
    """
    gate = safety_gate or SafetyGate()

    app = FastAPI(
        title="Smart Factory IoT Gateway API",
        version="0.1.0",
        description="MQTT ingestion gateway for ESP32-uKit Bridge.",
    )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        count = await store.count()
        dropped = dropped_count_ref.get("dropped", 0) if dropped_count_ref else 0
        hw = await store.high_watermark()
        return {
            "status": "ok",
            "event_count": count,
            "high_watermark": hw,
            "queue_dropped_count": dropped,
        }

    @app.get("/events")
    async def list_events(
        device_id: str | None = Query(None, description="Filter by device ID"),
        event_type: str | None = Query(None, description="Filter by event type"),
        limit: int = Query(100, ge=1, le=10000, description="Max events to return"),
    ) -> dict[str, Any]:
        events = await store.query(
            device_id=device_id, event_type=event_type, limit=limit
        )
        return {"events": events, "count": len(events)}

    @app.get("/events/{event_id}")
    async def get_event(event_id: str) -> dict[str, Any]:
        event = await store.get(event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")
        return event

    @app.get("/snapshot")
    async def get_snapshot(
        since_sequence: int = Query(
            0, ge=0,
            description="Return events with sequence > N. Use 0 for full snapshot. "
                        "Clients reconnecting should pass their last-known sequence."
        ),
        limit: int = Query(
            1000, ge=1, le=10000,
            description="Max events to return. On overflow, clients see a "
                        "sequence gap and must request a fresh full snapshot."
        ),
    ) -> dict[str, Any]:
        """Full scene snapshot for client initialization or resync after disconnect.

        Returns a deterministic ordered event log plus authoritative state anchors:

        - high_watermark: highest confirmed sequence in the store. Clients can
          use this to detect gaps (e.g. watermark > max(event sequence they have)
          signals missing events and a fresh full snapshot is needed).
        - events: events with sequence > since_sequence, sorted by sequence ascending.
          Empty when limit=0.
        - per_device_latest: one event per device_id — the most recent event
          for each device (by sequence). Gives clients current-state without
          replaying the full log.
        - overflow: True when the store holds more than `limit` events; the
          client should request a full snapshot (since_sequence=0) to avoid
          state gaps.
        - overflow_limit: the limit value used for this response.

        Replay protocol for reconnecting clients:
          1. Call GET /snapshot?since_sequence=<last_seq>
          2. If overflow=True OR response events have gaps → retry with since_sequence=0
          3. Apply snapshot events to local state
          4. Subscribe to WebSocket for live events with sequence > high_watermark
        """
        hw = await store.high_watermark()
        total = await store.count()
        overflow = total > limit

        events = []
        if since_sequence == 0:
            # Full snapshot: return up to limit sorted ascending (for deterministic replay)
            events = await store.query(limit=limit)
            events = sorted(events, key=lambda e: e.get("sequence", 0))
        elif since_sequence > 0:
            # Incremental: return events after cursor (store already sorts ASC)
            events = await store.query(since_sequence=since_sequence, limit=limit)

        # Per-device latest state — only on full snapshot to avoid extra DB queries
        per_device_latest = {}
        if since_sequence == 0:
            latest_map = await store.per_device_latest()
            per_device_latest = latest_map

        return {
            "high_watermark": hw,
            "snapshot_count": len(events),
            "events": events,
            "per_device_latest": per_device_latest,
            "overflow": overflow,
            "overflow_limit": limit,
        }

    @app.get("/metrics")
    async def get_metrics(
        queue_dropped_count: int = Query(
            0, ge=0,
            description="Number of events dropped by the write queue this reporting period. "
                        "Clients should track this across calls to detect drops."
        ),
    ) -> dict[str, Any]:
        """Expose latency histograms, jitter, stale event rate, out-of-order rate,
        and queue overflow count.

        Metrics reflect only events that were SUCCESSFULLY PERSISTED (not dropped
        by the write queue). queue_dropped_count is a cumulative counter maintained
        by the caller (gateway) that must be passed in from the /health endpoint
        or tracked client-side — it is not internal to this endpoint to keep
        the store layer stateless.
        """
        base = metrics.snapshot() if metrics is not None else {
            "latency_ms": {},
            "jitter_ms": {},
            "stale_event_count": 0,
            "out_of_order_event_count": 0,
            "unsynchronized_event_count": 0,
            "last_event_ms": {},
        }
        base["queue_dropped_count"] = queue_dropped_count
        return base

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "service": "Smart Factory IoT Gateway",
            "version": "0.1.0",
            "docs": "/docs",
        }

    # Safety Gate endpoints
    @app.get("/safety-gate/status")
    async def safety_gate_status() -> dict[str, Any]:
        """Get current safety gate status (non-sensitive)."""
        return gate.get_status()

    @app.get("/safety-gate/audit-log")
    async def safety_gate_audit_log(
        limit: int = Query(100, ge=1, le=10000, description="Max entries to return")
    ) -> dict[str, Any]:
        """Get safety gate audit log (non-sensitive metadata only).

        Returns only envelope metadata: decision_id, command_id, verdict,
        reason_code, confidence, timestamp, issuer. Command arguments are
        NOT included to protect secrets.
        """
        log = gate.audit_log
        # Return most recent entries first
        entries = [d.to_dict() for d in log[-limit:]]
        return {"audit_log": entries, "count": len(entries)}

    @app.post("/safety-gate/emergency-stop")
    async def set_emergency_stop(
        active: bool,
        _token: str = Depends(_require_operator_token),
    ) -> dict[str, str]:
        """Activate or deactivate emergency stop.

        Requires X-Operator-Token header matching SAFETY_OPERATOR_TOKEN env var.
        Software cannot remotely clear a hardware E-stop.
        """
        gate.set_emergency_stop(active)
        return {"emergency_stop_active": str(active).lower()}

    @app.post("/safety-gate/interlock/{device_id}")
    async def set_interlock(
        device_id: str,
        blocked: bool,
        _token: str = Depends(_require_operator_token),
    ) -> dict[str, str]:
        """Set interlock state for a device.

        Requires X-Operator-Token header matching SAFETY_OPERATOR_TOKEN env var.
        Hardware interlocks cannot be cleared by software — they must be cleared
        physically at the device.
        """
        if blocked:
            gate.set_interlock(device_id, True)
        else:
            gate.clear_interlock(device_id)
        return {"device_id": device_id, "interlock_active": str(blocked).lower()}

    @app.post("/safety-gate/operator-override")
    async def operator_override(
        _token: str = Depends(_require_operator_token),
    ) -> dict[str, str]:
        """Activate operator override mode (can only HOLD, not PERMIT).

        Requires X-Operator-Token header matching SAFETY_OPERATOR_TOKEN env var.

        Operator override temporarily pauses commands, requiring
        re-authorization before any command can proceed.
        """
        gate.activate_operator_override()
        return {"status": "operator_override_active", "authorization_required": "true"}

    @app.post("/safety-gate/authorize")
    async def authorize(
        _token: str = Depends(_require_operator_token),
    ) -> dict[str, str]:
        """Authorize commands after operator override.

        Requires X-Operator-Token header matching SAFETY_OPERATOR_TOKEN env var.

        Must be called after operator override to allow PERMIT decisions.
        This implements mandatory re-authorization requirement.
        """
        gate.authorize_after_override()
        return {"status": "authorized"}

    return app
