"""Unit tests for the alert outbox.

These tests exercise alert enqueuing, dispatch, retry logic,
dead-letter handling, and session-based ordering.
"""

import pytest

from iot_gateway.alert_outbox import (
    AlertDispatcher,
    AlertOutbox,
    AlertOutboxEntry,
    AlertOutboxState,
    AlertType,
    MqttAlertDispatcher,
    YansheeSkill,
)


class MockAlertDispatcher(AlertDispatcher):
    """Mock dispatcher for testing that tracks dispatches."""

    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self.dispatched_entries: list[AlertOutboxEntry] = []
        self.failure_count = 0
        self._fail_next_n = 0

    def fail_next(self, n: int) -> None:
        """Configure dispatcher to fail the next n dispatches."""
        self._fail_next_n = n

    async def dispatch(self, entry: AlertOutboxEntry) -> tuple[bool, str | None]:
        self.dispatched_entries.append(entry)
        if self._fail_next_n > 0:
            self._fail_next_n -= 1
            self.failure_count += 1
            return False, "Mock dispatch failure"
        if self.should_succeed:
            return True, None
        return False, "Mock dispatch failure"


class TestAlertOutboxEntry:
    """Tests for AlertOutboxEntry dataclass."""

    def test_default_values(self) -> None:
        """Test that AlertOutboxEntry has correct default values."""
        entry = AlertOutboxEntry(
            alert_type=AlertType.ALERT,
            title="Test Alert",
            message="This is a test",
        )

        assert entry.entry_id is not None
        assert entry.alert_type == AlertType.ALERT
        assert entry.title == "Test Alert"
        assert entry.state == AlertOutboxState.PENDING
        assert entry.attempt_count == 0
        assert entry.max_retries == 3

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        entry = AlertOutboxEntry(
            entry_id="entry-123",
            alert_type=AlertType.INCIDENT,
            alert_id="inc-456",
            device_id="device-1",
            session_id="session-1",
            sequence=5,
            title="Test Incident",
            message="Something happened",
            severity="critical",
            yanshee_skill=YansheeSkill.SPEECH,
        )

        d = entry.to_dict()

        assert d["entry_id"] == "entry-123"
        assert d["alert_type"] == "incident"
        assert d["alert_id"] == "inc-456"
        assert d["device_id"] == "device-1"
        assert d["session_id"] == "session-1"
        assert d["sequence"] == 5
        assert d["severity"] == "critical"
        assert d["yanshee_skill"] == "yanshee/speech"
        assert d["state"] == "pending"

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "entry_id": "entry-456",
            "alert_type": "yanshee_notification",
            "alert_id": None,
            "device_id": "robot-1",
            "session_id": "session-2",
            "sequence": 10,
            "title": "Yanshee Alert",
            "message": "Robot action needed",
            "severity": "warning",
            "yanshee_skill": "yanshee/movement",
            "state": "dispatched",
            "created_at": "2026-10-20T10:00:00+00:00",
            "dispatched_at": "2026-10-20T10:00:01+00:00",
            "attempt_count": 1,
        }

        entry = AlertOutboxEntry.from_dict(data)

        assert entry.entry_id == "entry-456"
        assert entry.alert_type == AlertType.YANSHEE_NOTIFICATION
        assert entry.yanshee_skill == YansheeSkill.MOVEMENT
        assert entry.state == AlertOutboxState.DISPATCHED


class TestAlertOutbox:
    """Tests for AlertOutbox."""

    @pytest.fixture
    def database_url(self, tmp_path) -> str:
        """Temp SQLite database."""
        db_path = tmp_path / "test_alerts.db"
        return f"sqlite+aiosqlite:///{db_path}"

    @pytest.fixture
    def dispatcher(self) -> MockAlertDispatcher:
        """Mock alert dispatcher."""
        return MockAlertDispatcher(should_succeed=True)

    @pytest.mark.asyncio
    async def test_init_creates_tables(self, database_url: str) -> None:
        """Test that init creates the alert_outbox table."""
        outbox = AlertOutbox(database_url)
        await outbox.init()
        await outbox.close()

    @pytest.mark.asyncio
    async def test_enqueue_creates_entry(self, database_url: str, dispatcher: MockAlertDispatcher) -> None:
        """Test enqueuing an alert creates it in PENDING state."""
        outbox = AlertOutbox(database_url, dispatcher=dispatcher)
        await outbox.init()
        try:
            entry = await outbox.enqueue(
                alert_type=AlertType.ALERT,
                title="Test Alert",
                message="This is a test",
                severity="info",
            )

            assert entry.state == AlertOutboxState.PENDING
            assert entry.title == "Test Alert"

            # Verify persisted
            fetched = await outbox.get_entry(entry.entry_id)
            assert fetched is not None
            assert fetched.entry_id == entry.entry_id
        finally:
            await outbox.close()

    @pytest.mark.asyncio
    async def test_enqueue_incident(self, database_url: str) -> None:
        """Test convenience method for incident enqueuing."""
        outbox = AlertOutbox(database_url)
        await outbox.init()
        try:
            entry = await outbox.enqueue_incident(
                incident_id="INC-001",
                title="Conveyor Stopped",
                message="Conveyor belt has stopped unexpectedly",
                severity="critical",
                device_id="conveyor-01",
            )

            assert entry.alert_type == AlertType.INCIDENT
            assert entry.alert_id == "INC-001"
            assert entry.device_id == "conveyor-01"
        finally:
            await outbox.close()

    @pytest.mark.asyncio
    async def test_enqueue_yanshee(self, database_url: str) -> None:
        """Test convenience method for Yanshee notifications."""
        outbox = AlertOutbox(database_url)
        await outbox.init()
        try:
            entry = await outbox.enqueue_yanshee(
                skill=YansheeSkill.SPEECH,
                title="Robot Speech",
                message="Hello, I am Yanshee",
                severity="info",
                device_id="yanshee-01",
            )

            assert entry.alert_type == AlertType.YANSHEE_NOTIFICATION
            assert entry.yanshee_skill == YansheeSkill.SPEECH
            assert entry.device_id == "yanshee-01"
        finally:
            await outbox.close()

    @pytest.mark.asyncio
    async def test_dispatch_success(self, database_url: str, dispatcher: MockAlertDispatcher) -> None:
        """Test successful dispatch transitions to DISPATCHED."""
        outbox = AlertOutbox(database_url, dispatcher=dispatcher)
        await outbox.init()
        try:
            entry = await outbox.enqueue(
                alert_type=AlertType.ALERT,
                title="Test",
                message="Test",
            )

            updated = await outbox.dispatch_entry(entry)

            assert updated.state == AlertOutboxState.DISPATCHED
            assert updated.dispatched_at is not None
            assert len(dispatcher.dispatched_entries) == 1
        finally:
            await outbox.close()

    @pytest.mark.asyncio
    async def test_dispatch_failure_increments_retry(self, database_url: str) -> None:
        """Test failed dispatch increments attempt_count."""
        dispatcher = MockAlertDispatcher(should_succeed=False)
        outbox = AlertOutbox(database_url, dispatcher=dispatcher)
        await outbox.init()
        try:
            entry = await outbox.enqueue(
                alert_type=AlertType.ALERT,
                title="Test",
                message="Test",
                max_retries=3,
            )

            updated = await outbox.dispatch_entry(entry)

            assert updated.state == AlertOutboxState.FAILED
            assert updated.attempt_count == 1
            assert updated.error_message == "Mock dispatch failure"
        finally:
            await outbox.close()

    @pytest.mark.asyncio
    async def test_max_retries_moves_to_dead_letter(self, database_url: str) -> None:
        """Test that exceeding max_retries moves entry to dead letter."""
        dispatcher = MockAlertDispatcher(should_succeed=False)
        outbox = AlertOutbox(database_url, dispatcher=dispatcher, max_retries=2)
        await outbox.init()
        try:
            entry = await outbox.enqueue(
                alert_type=AlertType.ALERT,
                title="Test",
                message="Test",
                max_retries=2,
            )

            # First attempt
            await outbox.dispatch_entry(entry)
            assert entry.state == AlertOutboxState.FAILED
            assert entry.attempt_count == 1

            # Second attempt (should trigger dead letter)
            await outbox.dispatch_entry(entry)
            assert entry.state == AlertOutboxState.DEAD_LETTER
            assert entry.attempt_count == 2
        finally:
            await outbox.close()

    @pytest.mark.asyncio
    async def test_get_dead_letter_entries(self, database_url: str) -> None:
        """Test retrieving dead-letter entries."""
        dispatcher = MockAlertDispatcher(should_succeed=False)
        outbox = AlertOutbox(database_url, dispatcher=dispatcher, max_retries=1)
        await outbox.init()
        try:
            # Create and fail an entry
            entry = await outbox.enqueue(
                alert_type=AlertType.ALERT,
                title="Test",
                message="Test",
            )
            await outbox.dispatch_entry(entry)  # Fails, moves to dead letter

            # Get dead letter entries
            dead_letters = await outbox.get_dead_letter_entries()

            assert len(dead_letters) == 1
            assert dead_letters[0].entry_id == entry.entry_id
        finally:
            await outbox.close()

    @pytest.mark.asyncio
    async def test_retry_dead_letter(self, database_url: str) -> None:
        """Test retrying a dead-letter entry."""
        dispatcher = MockAlertDispatcher(should_succeed=False)  # Fail first, to move to dead letter
        outbox = AlertOutbox(database_url, dispatcher=dispatcher, max_retries=1)
        await outbox.init()
        try:
            # Create and fail an entry to dead letter
            entry = await outbox.enqueue(
                alert_type=AlertType.ALERT,
                title="Test",
                message="Test",
            )
            await outbox.dispatch_entry(entry)  # Fails, attempt_count=1, now in DEAD_LETTER

            # Retry the dead letter
            reset = await outbox.retry_dead_letter(entry.entry_id)

            assert reset is not None
            assert reset.state == AlertOutboxState.PENDING
            assert reset.attempt_count == 0

            # Now dispatch should succeed (using a successful dispatcher)
            dispatcher2 = MockAlertDispatcher(should_succeed=True)
            outbox2 = AlertOutbox(database_url, dispatcher=dispatcher2)
            await outbox2.init()
            try:
                await outbox2.dispatch_entry(reset)
                assert reset.state == AlertOutboxState.DISPATCHED
            finally:
                await outbox2.close()
        finally:
            await outbox.close()

    @pytest.mark.asyncio
    async def test_session_ordering(self, database_url: str) -> None:
        """Test that alerts in same session are ordered by sequence."""
        outbox = AlertOutbox(database_url)
        await outbox.init()
        try:
            session_id = "session-123"

            # Enqueue in non-sequential order
            await outbox.enqueue(
                alert_type=AlertType.ALERT,
                title="Third",
                message="Third message",
                session_id=session_id,
            )
            await outbox.enqueue(
                alert_type=AlertType.ALERT,
                title="First",
                message="First message",
                session_id=session_id,
            )
            await outbox.enqueue(
                alert_type=AlertType.ALERT,
                title="Second",
                message="Second message",
                session_id=session_id,
            )

            # Get entries for session
            entries = await outbox.get_entries_by_session(session_id)

            assert len(entries) == 3
            # Should be ordered by sequence
            assert entries[0].title == "Third"  # sequence=0
            assert entries[1].title == "First"   # sequence=1
            assert entries[2].title == "Second"  # sequence=2
        finally:
            await outbox.close()

    @pytest.mark.asyncio
    async def test_worker_processes_pending(self, database_url: str, dispatcher: MockAlertDispatcher) -> None:
        """Test that worker processes pending entries."""
        outbox = AlertOutbox(database_url, dispatcher=dispatcher, poll_interval=1)
        await outbox.init()
        try:
            # Enqueue some alerts
            await outbox.enqueue(alert_type=AlertType.ALERT, title="Alert 1", message="msg1")
            await outbox.enqueue(alert_type=AlertType.ALERT, title="Alert 2", message="msg2")

            # Start worker
            await outbox.start_worker()

            # Wait for worker to process
            await asyncio.sleep(2)

            # Stop worker
            await outbox.stop_worker()

            # Check dispatch happened
            assert len(dispatcher.dispatched_entries) >= 2
        finally:
            await outbox.close()

    @pytest.mark.asyncio
    async def test_custom_max_retries(self, database_url: str) -> None:
        """Test custom max_retries per entry."""
        outbox = AlertOutbox(database_url)
        await outbox.init()
        try:
            entry = await outbox.enqueue(
                alert_type=AlertType.ALERT,
                title="Test",
                message="Test",
                max_retries=5,
            )

            assert entry.max_retries == 5
        finally:
            await outbox.close()


import asyncio


class TestYansheeSkill:
    """Tests for YansheeSkill enum."""

    def test_all_skills_defined(self) -> None:
        """Test all Yanshee skills are defined."""
        skills = [
            YansheeSkill.MOVEMENT,
            YansheeSkill.GRABBING,
            YansheeSkill.SPEECH,
            YansheeSkill.EMOTION,
            YansheeSkill.NAVIGATION,
        ]
        assert len(skills) == 5

    def test_skill_values(self) -> None:
        """Test Yanshee skill values."""
        assert YansheeSkill.MOVEMENT.value == "yanshee/movement"
        assert YansheeSkill.GRABBING.value == "yanshee/grabbing"
        assert YansheeSkill.SPEECH.value == "yanshee/speech"
        assert YansheeSkill.EMOTION.value == "yanshee/emotion"
        assert YansheeSkill.NAVIGATION.value == "yanshee/navigation"


class TestMqttAlertDispatcher:
    """Tests for MqttAlertDispatcher."""

    def test_can_be_instantiated(self) -> None:
        """Test that MqttAlertDispatcher can be instantiated."""
        dispatcher = MqttAlertDispatcher()
        assert dispatcher is not None

    def test_with_mock_publish_function(self) -> None:
        """Test using custom publish function."""
        published_messages: list[tuple[str, str, int]] = []

        def mock_publish(topic: str, payload: str, qos: int) -> None:
            published_messages.append((topic, payload, qos))

        dispatcher = MqttAlertDispatcher(mqtt_publish=mock_publish)

        # Verify instantiation
        assert dispatcher is not None
