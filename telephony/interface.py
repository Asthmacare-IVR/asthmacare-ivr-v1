"""
Telephony Interface (Contract)

This module will define the abstract boundary between the Queue Engine and
any concrete telephony implementation (SIM900A, Cloud IVR, SIP, Asterisk,
Mock).

Per ADR-001, this is an architectural contract, not a runtime pipeline stage:

    Queue Engine --> Telephony Interface (Contract) <-- SIM900A Adapter
                                                     <-- (future adapters)

Status: Phase 2 placeholder. The Queue Engine must never import a concrete
adapter directly — only this interface.

The actual contract (abstract methods, e.g. for sending SMS, placing/
receiving calls, DTMF handling) is designed and documented in
SYSTEM_ARCHITECTURE.md at Phase 3, and implemented when Phase 7 – Telephony
Adapter begins. No methods are defined yet — adding them here now would be
runtime logic ahead of its approved phase.
"""
