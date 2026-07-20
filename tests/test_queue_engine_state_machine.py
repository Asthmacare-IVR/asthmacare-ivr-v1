"""Contract tests for Queue State Machine — QUEUE_RULES.md §5.3, ADR-004."""

import pytest
from database.domain import QueueState
from queue_engine.state_machine import QueueStateMachine, StateMachineError


@pytest.fixture
def sm():
    return QueueStateMachine()


class TestValidTransitions:
    def test_requested_to_admitted(self, sm):
        sm.assert_valid(QueueState.REQUESTED, QueueState.ADMITTED)

    def test_requested_to_expired(self, sm):
        sm.assert_valid(QueueState.REQUESTED, QueueState.EXPIRED)

    def test_admitted_to_waiting(self, sm):
        sm.assert_valid(QueueState.ADMITTED, QueueState.WAITING)

    def test_waiting_to_notified(self, sm):
        sm.assert_valid(QueueState.WAITING, QueueState.NOTIFIED)

    def test_waiting_to_cancelled(self, sm):
        sm.assert_valid(QueueState.WAITING, QueueState.CANCELLED)

    def test_notified_to_confirmed(self, sm):
        sm.assert_valid(QueueState.NOTIFIED, QueueState.CONFIRMED)

    def test_notified_to_cancelled(self, sm):
        sm.assert_valid(QueueState.NOTIFIED, QueueState.CANCELLED)

    def test_notified_to_no_show(self, sm):
        sm.assert_valid(QueueState.NOTIFIED, QueueState.NO_SHOW)

    def test_confirmed_to_in_service(self, sm):
        sm.assert_valid(QueueState.CONFIRMED, QueueState.IN_SERVICE)

    def test_confirmed_to_no_show(self, sm):
        sm.assert_valid(QueueState.CONFIRMED, QueueState.NO_SHOW)

    def test_in_service_to_completed(self, sm):
        sm.assert_valid(QueueState.IN_SERVICE, QueueState.COMPLETED)


class TestInvalidTransitions:
    """ADR-004: IN_SERVICE → CANCELLED is forbidden."""

    def test_in_service_to_cancelled_raises(self, sm):
        with pytest.raises(StateMachineError, match="not permitted"):
            sm.assert_valid(QueueState.IN_SERVICE, QueueState.CANCELLED)

    def test_completed_to_anything_raises(self, sm):
        with pytest.raises(StateMachineError, match="terminal"):
            sm.assert_valid(QueueState.COMPLETED, QueueState.WAITING)

    def test_no_show_to_anything_raises(self, sm):
        with pytest.raises(StateMachineError, match="terminal"):
            sm.assert_valid(QueueState.NO_SHOW, QueueState.REQUESTED)

    def test_cancelled_to_anything_raises(self, sm):
        with pytest.raises(StateMachineError, match="terminal"):
            sm.assert_valid(QueueState.CANCELLED, QueueState.WAITING)

    def test_expired_to_anything_raises(self, sm):
        with pytest.raises(StateMachineError, match="terminal"):
            sm.assert_valid(QueueState.EXPIRED, QueueState.ADMITTED)

    def test_waiting_to_in_service_direct_raises(self, sm):
        with pytest.raises(StateMachineError, match="not permitted"):
            sm.assert_valid(QueueState.WAITING, QueueState.IN_SERVICE)

    def test_requested_to_waiting_direct_raises(self, sm):
        with pytest.raises(StateMachineError, match="not permitted"):
            sm.assert_valid(QueueState.REQUESTED, QueueState.WAITING)


class TestTransitionResult:
    def test_allowed_returns_allowed(self, sm):
        result = sm.validate(QueueState.WAITING, QueueState.NOTIFIED)
        assert result == "ALLOWED"

    def test_forbidden_returns_forbidden(self, sm):
        result = sm.validate(QueueState.WAITING, QueueState.COMPLETED)
        assert result == "FORBIDDEN"

    def test_terminal_returns_already_terminal(self, sm):
        result = sm.validate(QueueState.COMPLETED, QueueState.WAITING)
        assert result == "ALREADY_TERMINAL"


class TestGetAllowedTargets:
    def test_requested_targets(self, sm):
        targets = sm.get_allowed_targets(QueueState.REQUESTED)
        assert targets == {QueueState.ADMITTED, QueueState.EXPIRED}

    def test_in_service_targets(self, sm):
        targets = sm.get_allowed_targets(QueueState.IN_SERVICE)
        assert targets == {QueueState.COMPLETED}

    def test_completed_targets_empty(self, sm):
        targets = sm.get_allowed_targets(QueueState.COMPLETED)
        assert targets == frozenset()
