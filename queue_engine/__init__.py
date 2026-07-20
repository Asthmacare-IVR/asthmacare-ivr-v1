"""
queue_engine/ — Core application logic for the AsthmaCare IVR Platform.

Per ADR-002 and ADR-006:
- Queue Engine, appointment workflow, queue algorithms, orchestration
- Business Rules implementation (BUSINESS_RULES.md)
- Must never import a concrete telephony adapter (SIM900A, Cloud IVR, etc.)
- Must never import a concrete repository (SQLite, PostgreSQL)
- Depends only on: telephony/interface.py, database/interfaces.py

R-004 RESOLVED: Renamed from queue/ to avoid shadowing stdlib queue module.
"""

# Queue Engine exports will be added as implementation proceeds
__all__ = []
