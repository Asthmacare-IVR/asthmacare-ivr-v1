"""
database/ — Repository Interface (contract) and concrete repository
implementations for the AsthmaCare IVR Platform.

Per SYSTEM_ARCHITECTURE.md §4 and DATABASE_DESIGN.md §5, this package is a
leaf boundary: nothing here depends on queue_engine, api/, dashboard/, or
telephony/. Callers (Queue Engine, Business Rules) depend only on the
abstract interfaces exported below, never on a concrete implementation
package (database.sqlite, database.memory).
"""

from database.domain import Patient, QueueEntry, QueueState, Visit, VisitType
from database.errors import (
    ConflictError,
    NotFoundError,
    RepositoryError,
    UnavailableError,
    UnknownRepositoryError,
    ValidationFailureError,
)
from database.interfaces import (
    PatientRepository,
    QueueEntryRepository,
    UnitOfWork,
    VisitRepository,
)

__all__ = [
    "Patient",
    "QueueEntry",
    "QueueState",
    "Visit",
    "VisitType",
    "RepositoryError",
    "NotFoundError",
    "ConflictError",
    "ValidationFailureError",
    "UnavailableError",
    "UnknownRepositoryError",
    "PatientRepository",
    "QueueEntryRepository",
    "VisitRepository",
    "UnitOfWork",
]
