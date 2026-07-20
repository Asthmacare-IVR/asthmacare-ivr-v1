"""
database.memory — Mock/In-Memory Repository (REPOSITORY_INTERFACE.md §11).

Satisfies the exact same Repository Interface and Error Contract as
database.sqlite, with zero real storage involved, so the Queue Engine and
Business Rules layers can be tested fast and deterministically
(REPOSITORY_INTERFACE.md §11, SQLITE_REPOSITORY_DESIGN.md §14).
"""

from database.memory.in_memory_repository import InMemoryStore
from database.memory.unit_of_work import InMemoryUnitOfWork

__all__ = ["InMemoryStore", "InMemoryUnitOfWork"]
