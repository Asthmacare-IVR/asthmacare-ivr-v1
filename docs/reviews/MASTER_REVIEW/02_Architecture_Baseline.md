# 02 — Architecture Baseline

The frozen architecture, as merged, consists of the following layers
(unchanged in substance by this restructuring — only file locations moved):

```
AsthmaCare-IVR/
├── docs/                 Frozen architecture contracts, ADRs, roadmap, reviews
├── backend/
│   ├── api/              Phase 2 placeholder — REST API (Phase 11)
│   ├── config/           Phase 2 placeholder — wiring for database.sqlite.factory
│   ├── dashboard/        Phase 2 placeholder — Admin Dashboard (Phase 10)
│   ├── assets/           Phase 2 placeholder — static assets
│   ├── scripts/          Phase 2 placeholder — operational scripts
│   └── logs/             Phase 2 placeholder — runtime log output
├── database/
│   ├── domain.py          Patient, QueueEntry, QueueState, Visit, VisitType
│   ├── errors.py          RepositoryError hierarchy
│   ├── interfaces.py      Abstract Repository / Unit of Work contracts
│   ├── sqlite/            Concrete SQLite Repository Interface implementation
│   └── memory/            In-Memory/Mock Repository (Queue Engine test double)
├── queue_engine/          Core orchestration (renamed from queue_engine, ADR-006)
│   ├── engine.py           QueueEngine — transitions, ordering, timeouts, retries, events
│   ├── state_machine.py    Transition validation (QUEUE_RULES.md §5.3)
│   ├── ordering.py         Computed FIFO/priority position
│   ├── retry_manager.py    Bounded notification retries
│   ├── timeout_manager.py  Admission/notification/confirmation timeouts
│   └── events.py           Plain-data domain events
├── telephony/
│   ├── domain.py, errors.py, interface.py   Abstract Telephony Interface
│                                             (no concrete adapter yet — Phase 7/8)
└── tests/                 Contract + unit + integration tests, both implementations
```

## Dependency rule (unchanged, verified during merge)

`queue_engine/` may depend on `database.interfaces` / `database.domain` and
`telephony.interface` only — never a concrete repository (`database.sqlite`,
`database.memory`) or a concrete telephony adapter. Verified by inspection:
`queue_engine/*.py` imports only `database.domain` and `database.interfaces`
(via `UnitOfWork`); no `database.sqlite.*` or `database.memory.*` import
appears anywhere under `queue_engine/`.

## Authority hierarchy (unchanged, from `docs/adr/DECISION_LOG.md`)

1. `BUSINESS_RULES.md` — authoritative for patient lifecycle, eligibility,
   workflow policy, business meaning.
2. `QUEUE_RULES.md` — authoritative for Queue Engine operational states,
   scheduling, ordering, notifications, transitions, execution mechanics.
3. The Queue Engine implements Business Rules but never redefines or
   overrides them.
4. Business Rules never define Queue Engine operational mechanics.
