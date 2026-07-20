"""
Retry Manager — QUEUE_RULES.md §7.

Tracks notification retry attempts per queue entry.
Bounded, countable, auditable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


class RetryExhaustedError(Exception):
    """Raised when maximum retry attempts have been consumed."""


@dataclass
class RetryState:
    """Mutable tracking of retries for a single entry."""
    entry_id: str
    attempts_made: int = 0
    max_attempts: int = 3  # Business Rules parameter, not hard-coded

    @property
    def has_retries_remaining(self) -> bool:
        return self.attempts_made < self.max_attempts

    @property
    def is_exhausted(self) -> bool:
        return self.attempts_made >= self.max_attempts

    def record_attempt(self) -> None:
        """Record one retry attempt. Raises if already exhausted."""
        if self.is_exhausted:
            raise RetryExhaustedError(
                f"Entry {self.entry_id}: max {self.max_attempts} retries exhausted"
            )
        self.attempts_made += 1


class RetryManager:
    """
    QUEUE_RULES.md §7: retry is defined only for NOTIFIED state.
    Each retry is a distinct, auditable event.
    """

    def __init__(self, default_max_attempts: int = 3) -> None:
        self.default_max_attempts = default_max_attempts
        self._states: dict[str, RetryState] = {}

    def get_state(self, entry_id: str) -> RetryState:
        """Get or create retry state for an entry."""
        if entry_id not in self._states:
            self._states[entry_id] = RetryState(
                entry_id=entry_id,
                max_attempts=self.default_max_attempts
            )
        return self._states[entry_id]

    def record_attempt(self, entry_id: str) -> None:
        """Record one retry attempt. Raises RetryExhaustedError if at limit."""
        state = self.get_state(entry_id)
        state.record_attempt()

    def is_exhausted(self, entry_id: str) -> bool:
        """Check if retries are exhausted for this entry."""
        return self.get_state(entry_id).is_exhausted

    def reset(self, entry_id: str) -> None:
        """Reset retry count (e.g., on successful confirmation)."""
        if entry_id in self._states:
            del self._states[entry_id]
