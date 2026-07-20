"""Tests for Queue Ordering — QUEUE_RULES.md §6."""

from datetime import datetime

import pytest
from database.domain import QueueEntry, QueueState
from queue_engine.ordering import QueueOrdering, OrderedEntry


def make_entry(entry_id: str, patient_id: str, timestamp: datetime, state: QueueState = QueueState.WAITING):
    return QueueEntry(
        entry_id=entry_id,
        patient_id=patient_id,
        queue_date=datetime.now().date(),
        queue_number=1,
        state=state,
        entry_timestamp=timestamp,
        last_updated_at=timestamp,
    )


class TestFIFOOrdering:
    def test_single_entry_position_one(self):
        ordering = QueueOrdering()
        entry = make_entry("e1", "p1", datetime(2026, 7, 20, 9, 0))
        result = ordering.compute_positions([entry])
        assert len(result) == 1
        assert result[0].position == 1
        assert result[0].entry.entry_id == "e1"

    def test_fifo_by_entry_timestamp(self):
        ordering = QueueOrdering()
        e1 = make_entry("e1", "p1", datetime(2026, 7, 20, 9, 0))
        e2 = make_entry("e2", "p2", datetime(2026, 7, 20, 9, 5))
        e3 = make_entry("e3", "p3", datetime(2026, 7, 20, 9, 10))

        result = ordering.compute_positions([e3, e1, e2])  # Shuffled input
        assert [r.entry.entry_id for r in result] == ["e1", "e2", "e3"]
        assert [r.position for r in result] == [1, 2, 3]

    def test_notified_entries_included(self):
        ordering = QueueOrdering()
        e1 = make_entry("e1", "p1", datetime(2026, 7, 20, 9, 0), QueueState.WAITING)
        e2 = make_entry("e2", "p2", datetime(2026, 7, 20, 9, 5), QueueState.NOTIFIED)

        result = ordering.compute_positions([e1, e2])
        assert len(result) == 2

    def test_terminal_states_excluded(self):
        ordering = QueueOrdering()
        e1 = make_entry("e1", "p1", datetime(2026, 7, 20, 9, 0), QueueState.WAITING)
        e2 = make_entry("e2", "p2", datetime(2026, 7, 20, 9, 5), QueueState.COMPLETED)
        e3 = make_entry("e3", "p3", datetime(2026, 7, 20, 9, 10), QueueState.CANCELLED)

        result = ordering.compute_positions([e1, e2, e3])
        assert len(result) == 1
        assert result[0].entry.entry_id == "e1"

    def test_get_position(self):
        ordering = QueueOrdering()
        e1 = make_entry("e1", "p1", datetime(2026, 7, 20, 9, 0))
        e2 = make_entry("e2", "p2", datetime(2026, 7, 20, 9, 5))

        assert ordering.get_position("e1", [e1, e2]) == 1
        assert ordering.get_position("e2", [e1, e2]) == 2
        assert ordering.get_position("e3", [e1, e2]) is None

    def test_get_next_to_call(self):
        ordering = QueueOrdering()
        e1 = make_entry("e1", "p1", datetime(2026, 7, 20, 9, 0))
        e2 = make_entry("e2", "p2", datetime(2026, 7, 20, 9, 5))

        next_entry = ordering.get_next_to_call([e1, e2])
        assert next_entry.entry_id == "e1"

    def test_get_next_to_call_empty(self):
        ordering = QueueOrdering()
        assert ordering.get_next_to_call([]) is None


class TestPriorityOverride:
    def test_custom_priority_key(self):
        """BUSINESS_RULES.md §5.3: emergency override inserts at front."""
        def emergency_first(entry: QueueEntry) -> tuple:
            # Simulate: emergency entries sort first, then FIFO
            is_emergency = entry.patient_id == "emergency"
            return (not is_emergency, entry.entry_timestamp)

        ordering = QueueOrdering(priority_key=emergency_first)
        e1 = make_entry("e1", "p1", datetime(2026, 7, 20, 9, 0))
        e2 = make_entry("e2", "emergency", datetime(2026, 7, 20, 9, 10))

        result = ordering.compute_positions([e1, e2])
        assert result[0].entry.entry_id == "e2"  # Emergency first
        assert result[1].entry.entry_id == "e1"
        assert result[0].position == 1
