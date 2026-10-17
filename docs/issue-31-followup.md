# Issue #31 — Event Store: Implementation Follow-Up

**Branch:** `docs/issue-31-event-store-followup`
**Reviewed against:** `docs/issue-31-event-store-contract.md` (master)
**Author:** Agent (coordinator)
**Reviewer:** vinhphan812
**Date:** 2026-10-17

---

## 1. Status Summary

The event store implementation has materially improved since the contract doc was written. Three of the six flagged gaps are **resolved**. The remaining gaps are narrower in scope and carry lower risk. The top three prioritized items are listed in §3 below.

---

## 2. Completed Items

| Gap (from contract doc) | Status | Evidence |
|---|---|---|
| **Atomic counter / `GatewayMetadata` table** | ✅ Resolved | `_increment_sequence()` uses atomic `UPDATE … RETURNING` against `gateway_metadata`. Two-session split in `insert_dict` is a minor atomicity concern but not a correctness defect. |
| **`TELEMETRY` and `HEARTBEAT` event types not wired** | ✅ Resolved | `event_normalizer.py` lines 24, 28 have regex patterns; `config.py` lines 40–41 have topic subscriptions. |
| **ADR-0005 `event_id` / `device_id` / `payload` / `mqtt_topic` / `mqtt_timestamp_ms` / `ingested_at`** | ✅ Verified | All fields present on `EventRecord` and `CanonicalEvent`. |
| **Schema migration for timing columns** | ✅ Resolved | `_migrate_schema()` uses `PRAGMA table_info` to detect and `ALTER TABLE ADD COLUMN` missing timing columns idempotently. |
| **`/snapshot` HTTP endpoint** | ✅ Implemented | `api.py` line 187: `GET /snapshot` returns `high_watermark`, `events`, `per_device_latest`, `overflow`, `snapshot_count`. |
| **Retention pruning** | ✅ Functional | `_prune_old_events()` runs inline post-insert; works correctly (verified by `test_bounded_retention`). |

---

## 3. Top 3 Remaining Items (Prioritized)

### P1 — Add `UNIQUE` constraint on `sequence` column

**Why it matters:** The `sequence` column has no uniqueness guard. A bug in `_increment_sequence()` or a race between two gateway instances could produce duplicate sequences. The `event_id` PK prevents duplicates of the same event, but a colliding sequence number is silently accepted and breaks client replay ordering.

**What to do:** Add `unique=True` to the `sequence` Column definition in `EventRecord`. Run a migration (via the existing `_migrate_schema()` path or a new idempotent add-unique step) to guard existing data.

```python
# In EventRecord:
sequence = Column(Integer, nullable=False, index=True, unique=True)
```

**Severity:** Medium. Low probability in single-instance deployments; a hard blocker for multi-instance deployments.

---

### P2 — Ensure `insert_dict` atomicity for insert + prune

**Why it matters:** `insert_dict` uses two independent `async with self._session_maker() as session` blocks — one for INSERT, one for `_prune_old_events()`. A process crash between them means the event is inserted but the old-event count exceeds `max_events` temporarily. This is recoverable (the next insert corrects it), but is not clean.

**What to do:** Merge the prune into the same transaction as the insert, or add a try/except guard that re-runs prune on startup. The simpler fix is to make prune a single `DELETE … WHERE sequence IN (SELECT … LIMIT excess)` wrapped in the same `async with session.begin()` block as the insert.

```python
async with self._session_maker() as session:
    async with session.begin():
        session.add(record)
        # Inline prune within same transaction
        total = (await session.execute(select(func.count()).select_from(EventRecord))).scalar() or 0
        if total > self._max_events:
            excess = total - self._max_events
            await session.execute(
                delete(EventRecord).where(
                    EventRecord.sequence.in_(
                        select(EventRecord.sequence).order_by(EventRecord.sequence.asc()).limit(excess)
                    )
                )
            )
        await session.commit()
```

**Severity:** Low. Correctness impact only on crash path; normal operation is unaffected.

---

### P3 — Quarantine table for malformed events (ADR-0005 alignment)

**Why it matters:** ADR-0005 §5 specifies quarantine for malformed events. Currently, events that fail normalization are logged only and dropped. A quarantine table would allow manual inspection and retry, improving debuggability in production.

**What to do:** Add a `malformed_events` table (mirrors `CanonicalEvent` fields plus an `error_message` TEXT column). In `event_normalizer.py`, catch normalization failures and insert into quarantine instead of logging and discarding.

**Severity:** Low. Operational quality of life; not blocking for core function.

---

## 4. Unchanged / Low-Priority Items

| Gap | Decision | Rationale |
|---|---|---|
| **No Alembic migrations** | Accept as-is | Module convention uses `create_all` + `_migrate_schema()`; Alembic adds complexity disproportionate to this module's schema churn rate. |
| **Inline retention vs. background job** | Accept as-is | `_prune_old_events()` correctness verified by `test_bounded_retention`. Background job adds worker complexity for marginal benefit. |
| **No dedicated snapshot table** | Accept as-is | `per_device_latest()` + `events` table queries achieve the same result without a separate materialized table. Simpler is better here. |
| **`trace_id` field in `CanonicalEvent`** | Accept as-is | Not in current `models.py`; not a blocking gap for v1. Can be added as part of a future tracing ADR. |

---

## 5. Verification Checklist

- [x] `GatewayMetadata` atomic counter: `_increment_sequence()` uses `UPDATE … RETURNING`
- [x] Migration: `_migrate_schema()` adds timing columns idempotently
- [x] `insert` / `insert_dict`: stores full `CanonicalEvent` dict
- [x] `query` with `device_id`, `event_type`, `since_sequence`, `limit`
- [x] `get` by `event_id`
- [x] `count`
- [x] `high_watermark`
- [x] `per_device_latest`
- [x] Retention pruning on insert
- [x] `/snapshot` HTTP endpoint (api.py line 187+)
- [x] Write queue + `_write_worker` in `gateway.py`
- [x] Unit tests for store: `test_insert_and_get`, `test_query_by_device_id`, `test_query_by_event_type`, `test_query_limit`, `test_count_returns_accurate_total`, `test_bounded_retention`, `test_get_nonexistent_returns_none`, `test_query_empty`, `test_sequence_ordering`
- [x] `TELEMETRY` / `HEARTBEAT` regex patterns in normalizer
- [ ] `UNIQUE` constraint on `sequence` — **pending**
- [ ] Atomic insert+prune in single transaction — **pending**
- [ ] Quarantine table for malformed events — **pending**

---

## 6. References

| Artifact | Location |
|---|---|
| EventStore source | `iot-gateway/src/iot_gateway/event_store.py` |
| CanonicalEvent model | `iot-gateway/src/iot_gateway/models.py` |
| Event normalizer | `iot-gateway/src/iot_gateway/event_normalizer.py` |
| Gateway orchestration | `iot-gateway/src/iot_gateway/gateway.py` |
| HTTP API (snapshot) | `iot-gateway/src/iot_gateway/api.py` |
| Store unit tests | `iot-gateway/tests/test_store.py` |
| ADR-0005 | `docs/adr/adr-0005-gateway-canonical-events.md` |
| Original contract | `docs/issue-31-event-store-contract.md` |
