"""
IVR session management for tracking call state, context, and retry counts.
"""

import time
import logging
from typing import Dict, Any, Optional
from ivr.models import IVRContext, IVRState

logger = logging.getLogger(__name__)


class IVRSession:
    """Represents an active IVR call session, tracking context, state, and retry metrics."""

    def __init__(self, session_id: str, call_id: str, phone_number: str, initial_state: IVRState = IVRState.START):
        """
        Initialize an IVR session.

        Args:
            session_id: Unique identifier for the session.
            call_id: Telephony call identifier.
            phone_number: Caller's phone number.
            initial_state: Starting state IVRState.
        """
        self.session_id = session_id
        self.call_id = call_id
        self.phone_number = phone_number
        self.context = IVRContext(call_id=call_id, phone_number=phone_number, current_state=initial_state)
        self.start_time = time.time()
        self.last_activity_time = self.start_time
        self.retry_counts: Dict[str, int] = {}
        self.is_active = True

    @property
    def current_state(self) -> IVRState:
        return self.context.current_state

    def update_state(self, new_state: IVRState) -> None:
        """Transition session context to a new state and update activity timestamps."""
        logger.info("Session %s transitioning state: %s -> %s", self.session_id, self.context.current_state.value, new_state.value)
        self.context.current_state = new_state
        self.last_activity_time = time.time()

    def increment_retry(self, state_name: Optional[str] = None) -> int:
        """
        Increment retry counter in context and local tracker.

        Args:
            state_name: Optional state name override.

        Returns:
            Updated retry count.
        """
        self.context.attempts += 1
        target = state_name or self.context.current_state.value
        current_count = self.retry_counts.get(target, 0) + 1
        self.retry_counts[target] = current_count
        self.last_activity_time = time.time()
        logger.info("Session %s retry count incremented to %d", self.session_id, current_count)
        return current_count

    def get_retry_count(self, state_name: Optional[str] = None) -> int:
        """Get current retry count for a state."""
        target = state_name or self.context.current_state.value
        return self.retry_counts.get(target, self.context.attempts)

    def reset_retry(self, state_name: Optional[str] = None) -> None:
        """Reset retry counters."""
        self.context.attempts = 0
        self.retry_counts.clear()

    def terminate(self) -> None:
        """Mark the session as inactive/terminated."""
        logger.info("Terminating IVR session %s", self.session_id)
        self.is_active = False
        self.last_activity_time = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Export session details as a dictionary."""
        return {
            "session_id": self.session_id,
            "call_id": self.call_id,
            "phone_number": self.phone_number,
            "current_state": self.context.current_state.value,
            "attempts": self.context.attempts,
            "start_time": self.start_time,
            "last_activity_time": self.last_activity_time,
            "is_active": self.is_active,
        }