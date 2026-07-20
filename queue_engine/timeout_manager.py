"""
Timeout Manager — QUEUE_RULES.md §8.

Detects timeout conditions for dwell durations.
Idempotent: repeated evaluation of already-timed-out entry is safe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Optional


class TimeoutType(Enum):
    ADMISSION_TIMEOUT = "admission_timeout"      # REQUESTED → EXPIRED
    NOTIFICATION_TIMEOUT = "notification_timeout"  # NOTIFIED → NO_SHOW
    CONFIRMATION_TIMEOUT = "confirmation_timeout"  # CONFIRMED → NO_SHOW


@dataclass(frozen=True)
class TimeoutConfig:
    """Business Rules-supplied parameters (QUEUE_RULES.md §8)."""
    admission_timeout: timedelta = timedelta(minutes=5)
    notification_timeout: timedelta = timedelta(minutes=5)
    confirmation_timeout: timedelta = timedelta(minutes=10)


class TimeoutManager:
    """
    QUEUE_RULES.md §8: timeout detection is Queue Engine responsibility.
    Idempotent evaluation — no duplicate events on re-check.
    """

    def __init__(
        self,
        config: TimeoutConfig,
        clock: Optional[Callable[[], datetime]] = None
    ) -> None:
        self.config = config
        self.clock = clock or datetime.now
        self._timed_out: set[str] = set()  # Track already-processed

    def check_admission_timeout(
        self,
        entry_id: str,
        requested_at: datetime
    ) -> bool:
        """Check if REQUESTED entry has exceeded admission window."""
        if entry_id in self._timed_out:
            return False  # Already processed (idempotent)

        elapsed = self.clock() - requested_at
        if elapsed > self.config.admission_timeout:
            self._timed_out.add(entry_id)
            return True
        return False

    def check_notification_timeout(
        self,
        entry_id: str,
        notified_at: datetime,
        retry_exhausted: bool
    ) -> bool:
        """
        Check if NOTIFIED entry has timed out.
        QUEUE_RULES.md §7: retries must be exhausted before timeout fires.
        """
        if entry_id in self._timed_out:
            return False

        if not retry_exhausted:
            return False  # Still have retries

        elapsed = self.clock() - notified_at
        if elapsed > self.config.notification_timeout:
            self._timed_out.add(entry_id)
            return True
        return False

    def check_confirmation_timeout(
        self,
        entry_id: str,
        confirmed_at: datetime
    ) -> bool:
        """Check if CONFIRMED entry has exceeded handoff window."""
        if entry_id in self._timed_out:
            return False

        elapsed = self.clock() - confirmed_at
        if elapsed > self.config.confirmation_timeout:
            self._timed_out.add(entry_id)
            return True
        return False
