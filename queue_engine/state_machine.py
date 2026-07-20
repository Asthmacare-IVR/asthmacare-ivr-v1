"""
Queue State Machine — QUEUE_RULES.md §5.2, §5.3, §9.

Validates state transitions. Immutable, side-effect-free.
Does NOT execute transitions — only validates permission.
"""

from __future__ import annotations

from typing import Final

from database.domain import QueueState, TERMINAL_QUEUE_STATES


# QUEUE_RULES.md §5.3 — canonical transition table (ADR-004 applied)
# IN_SERVICE → CANCELLED removed per ADR-004
_VALID_TRANSITIONS: Final[dict[QueueState, frozenset[QueueState]]] = {
    QueueState.REQUESTED: frozenset({QueueState.ADMITTED, QueueState.EXPIRED}),
    QueueState.ADMITTED: frozenset({QueueState.WAITING}),
    QueueState.WAITING: frozenset({QueueState.NOTIFIED, QueueState.CANCELLED}),
    QueueState.NOTIFIED: frozenset({QueueState.CONFIRMED, QueueState.CANCELLED, QueueState.NO_SHOW}),
    QueueState.CONFIRMED: frozenset({QueueState.IN_SERVICE, QueueState.NO_SHOW}),
    QueueState.IN_SERVICE: frozenset({QueueState.COMPLETED}),
    # Terminal states: no outbound transitions (QUEUE_RULES.md §5.4)
    QueueState.COMPLETED: frozenset(),
    QueueState.NO_SHOW: frozenset(),
    QueueState.CANCELLED: frozenset(),
    QueueState.EXPIRED: frozenset(),
}


class StateMachineError(Exception):
    """Raised when an invalid state transition is requested."""


class QueueStateMachine:
    """
    Validates transitions per frozen QUEUE_RULES.md §5.3.

    Thread-safe (immutable, no shared state).
    """

    def validate(self, current: QueueState, proposed: QueueState) -> str:
        """Check if transition is permitted. Returns result name."""
        if current in TERMINAL_QUEUE_STATES and current != proposed:
            return "ALREADY_TERMINAL"
        if proposed in _VALID_TRANSITIONS.get(current, frozenset()):
            return "ALLOWED"
        return "FORBIDDEN"

    def assert_valid(self, current: QueueState, proposed: QueueState) -> None:
        """Validate and raise StateMachineError if forbidden."""
        result = self.validate(current, proposed)
        if result == "ALREADY_TERMINAL":
            raise StateMachineError(
                f"Cannot transition from terminal state {current.value}"
            )
        if result == "FORBIDDEN":
            raise StateMachineError(
                f"Transition {current.value} → {proposed.value} is not permitted"
            )

    def get_allowed_targets(self, current: QueueState) -> frozenset[QueueState]:
        """Get all valid next states from current state."""
        return _VALID_TRANSITIONS.get(current, frozenset())
