# Risk Register

| ID | Risk | Phase Introduced | Likelihood | Impact | Mitigation | Status |
|---|---|---|---|---|---|---|
| R-001 | Windows-native serial handling (pyserial) may behave differently than on Linux/Pi, causing rework at Phase 6 or 12 | 1 | Medium | Medium | Keep Telephony Adapter interface narrow and OS-agnostic; revisit WSL2 decision (D-002) before Phase 6 | Open |
| R-002 | SQLite file could be accidentally committed to Git, exposing patient data | 1 | Low | High | `.gitignore` excludes `*.db` / `*.sqlite3`; enforce in code review | Mitigated |
| R-003 | Hardware delivery delay (SIM900A, Pi) stalls Phases 6/12 | 1 | Medium | Medium | Software phases (2–5, 7–11 partially) sequenced to not depend on hardware arrival | Monitored |
| R-004 | Top-level `queue/` directory/package shadows Python's standard library `queue` module, risking import shadowing bugs (affects asyncio, concurrent.futures, and any library doing `import queue`) | 2 | Medium | Medium-High | Flagged in DECISION_LOG.md; must be resolved (rename or src-layout) with an ADR before Phase 8 – Queue Engine implementation begins | Open |
