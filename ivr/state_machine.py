"""IVR State Machine — docs/IVR_STATE_MACHINE.md.

Validates state transitions. Immutable, side-effect-free. Does NOT
execute transitions or hold call state — only validates permission and
computes the successor state on the linear happy path. Mirrors the
validate-only pattern used by `queue_engine/state_machine.py`.
"""

from __future__ import annotations

from typing import Final

from ivr.exceptions import InvalidTransitionError
from ivr.models import IVRState

# The happy-path successor of each state. FAILED's successor (END) is
# included here too: failing a call still ends in a graceful hangup, not
# an alternate terminal state.
_LINEAR_TRANSITIONS: Final[dict[IVRState, IVRState]] = {
    IVRState.START: IVRState.WELCOME,
    IVRState.WELCOME: IVRState.PATIENT_IDENTIFICATION,
    IVRState.PATIENT_IDENTIFICATION: IVRState.PATIENT_VERIFIED,
    IVRState.PATIENT_VERIFIED: IVRState.QUEUE_REGISTRATION,
    IVRState.QUEUE_REGISTRATION: IVRState.CONFIRMATION,
    IVRState.CONFIRMATION: IVRState.CALL_COMPLETED,
    IVRState.CALL_COMPLETED: IVRState.END,
    IVRState.FAILED: IVRState.END,
}

# The only true terminal state: no outbound transitions at all.
TERMINAL_STATES: Final[frozenset[IVRState]] = frozenset({IVRState.END})

# States from which a failure branch cannot be taken: already-terminal
# END, and FAILED itself (a call can fail only once).
_NON_FAILABLE_STATES: Final[frozenset[IVRState]] = frozenset({IVRState.FAILED, IVRState.END})


class IVRStateMachine:
    """Validates transitions per the frozen state diagram above.

    Thread-safe (immutable, no shared state).
    """

    def get_next(self, current: IVRState) -> IVRState | None:
        """Return the single successor state on the linear path, or
        `None` if `current` is terminal."""
        return _LINEAR_TRANSITIONS.get(current)

    def can_fail(self, current: IVRState) -> bool:
        """Whether `current` may transition directly to FAILED."""
        return current not in _NON_FAILABLE_STATES

    def get_allowed_targets(self, current: IVRState) -> frozenset[IVRState]:
        """All valid next states from `current`."""
        targets: set[IVRState] = set()
        successor = self.get_next(current)
        if successor is not None:
            targets.add(successor)
        if self.can_fail(current):
            targets.add(IVRState.FAILED)
        return frozenset(targets)

    def validate(self, current: IVRState, proposed: IVRState) -> str:
        """Check if a transition is permitted. Returns a result name."""
        if current in TERMINAL_STATES:
            return "ALREADY_TERMINAL"
        if proposed in self.get_allowed_targets(current):
            return "ALLOWED"
        return "FORBIDDEN"

    def assert_valid(self, current: IVRState, proposed: IVRState) -> None:
        """Validate and raise InvalidTransitionError if forbidden."""
        result = self.validate(current, proposed)
        if result == "ALREADY_TERMINAL":
            raise InvalidTransitionError(f"Cannot transition from terminal state {current.value}")
        if result == "FORBIDDEN":
            raise InvalidTransitionError(
                f"Transition {current.value} → {proposed.value} is not permitted"
            )

    def is_terminal(self, state: IVRState) -> bool:
        """Whether `state` is the workflow's terminal state."""
        return state in TERMINAL_STATES
