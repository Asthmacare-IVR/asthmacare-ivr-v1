"""
Queue Ordering — QUEUE_RULES.md §6.

Position is COMPUTED, not stored (§6.3).
Deterministic, stable ordering with Business Rules priority hook.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional, Sequence

from database.domain import QueueEntry, QueueState


# QUEUE_RULES.md §6.1: these states participate in ordering
ORDERABLE_STATES: frozenset[QueueState] = frozenset({
    QueueState.WAITING,
    QueueState.NOTIFIED,
})


@dataclass(frozen=True)
class OrderedEntry:
    """A queue entry with its computed 1-based position."""
    entry: QueueEntry
    position: int


# Default priority key type
PriorityKey = Callable[[QueueEntry], tuple]


class QueueOrdering:
    """
    Computes queue positions. Deterministic and stable (QUEUE_RULES.md §6.2).

    BUSINESS_RULES.md §5.2: priority handling modifies position, not bypass.
    BUSINESS_RULES.md §5.3: emergency override inserts at front.
    """

    def __init__(
        self,
        priority_key: Optional[PriorityKey] = None
    ) -> None:
        self.priority_key = priority_key or self._default_priority_key

    @staticmethod
    def _default_priority_key(entry: QueueEntry) -> tuple:
        """
        FIFO fallback: (entry_timestamp, entry_id) for deterministic tie-breaking.
        QUEUE_RULES.md §6.2: ties broken by timestamp, then stable secondary key.
        """
        return (entry.entry_timestamp, entry.entry_id)

    def compute_positions(
        self,
        entries: Sequence[QueueEntry]
    ) -> list[OrderedEntry]:
        """
        Compute 1-based positions for all orderable entries.

        QUEUE_RULES.md §6.3: position is derived, not authoritative state.
        """
        # Filter to orderable states only
        orderable = [e for e in entries if e.state in ORDERABLE_STATES]

        # Sort by priority key — deterministic and stable
        sorted_entries = sorted(orderable, key=self.priority_key)

        return [
            OrderedEntry(entry=entry, position=i + 1)
            for i, entry in enumerate(sorted_entries)
        ]

    def get_position(
        self,
        entry_id: str,
        entries: Sequence[QueueEntry]
    ) -> Optional[int]:
        """Get position for specific entry, or None if not orderable."""
        for ordered in self.compute_positions(entries):
            if ordered.entry.entry_id == entry_id:
                return ordered.position
        return None

    def get_next_to_call(
        self,
        entries: Sequence[QueueEntry]
    ) -> Optional[QueueEntry]:
        """Get the entry at position 1 (front of queue), or None."""
        ordered = self.compute_positions(entries)
        return ordered[0].entry if ordered else None
