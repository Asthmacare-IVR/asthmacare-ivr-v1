"""
database.sqlite — the pilot's concrete Repository Interface implementation
(SQLITE_REPOSITORY_DESIGN.md).

This package is a leaf: it may depend on sqlite3, but nothing above the
Database boundary (queue/, api/, dashboard/) may import anything from this
package directly (DATABASE_DESIGN.md §5). Callers should only ever obtain
instances of this package's classes through `database.sqlite.factory`,
which returns them typed as the abstract interfaces in `database.interfaces`.
"""

from database.sqlite.factory import SqliteConfig, SqliteRepositoryProvider, build_unit_of_work
from database.sqlite.unit_of_work import SqliteRepositories, SqliteUnitOfWork

__all__ = [
    "SqliteConfig",
    "SqliteRepositoryProvider",
    "build_unit_of_work",
    "SqliteRepositories",
    "SqliteUnitOfWork",
]
