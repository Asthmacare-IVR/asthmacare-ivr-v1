# PARITY_FIX.md

## Scope

Small, isolated bug fix. Two files changed only:

- `database/memory/in_memory_repository.py`
- `tests/test_contract_patient_repository.py`

No architecture documents, ADRs, `telephony/`, `database/sqlite/`, or
`database/interfaces.py` were touched.

---

## Original bug

`InMemoryPatientRepository.update()` allowed a patient to be updated to a
phone number already held by a *different* patient, without raising an
error. `SqlitePatientRepository.update()`, given the same input, correctly
raised `ConflictError`.

Verified directly before writing the fix:

```
IN-MEMORY: update with duplicate phone SUCCEEDED (no ConflictError raised)
SQLITE:    update raised ConflictError: UNIQUE constraint failed: patients.phone_number
```

## Root cause

`InMemoryPatientRepository.add()` already checked phone-number uniqueness
via `find_by_phone_number()` before inserting. `update()` never performed
the equivalent check — it only verified that `patient_id` already existed,
then unconditionally overwrote the stored record:

```python
def update(self, patient: Patient) -> Patient:
    if patient.patient_id not in self._store.patients:
        raise NotFoundError(...)
    self._store.patients[patient.patient_id] = patient   # no phone check
```

## Why SQLite and InMemory behaved differently

`SqlitePatientRepository` never implements uniqueness logic in Python at
all — it relies entirely on the database schema:

```sql
CREATE UNIQUE INDEX idx_patients_phone_number ON patients(phone_number)
```

Any `INSERT` or `UPDATE` that would produce a duplicate `phone_number`
raises `sqlite3.IntegrityError`, which `error_translation.py` converts to
`ConflictError`. This constraint is enforced by the storage engine on
every write path automatically, including `UPDATE`.

`InMemoryPatientRepository` has no underlying engine to enforce this — it
is a plain Python dict, so *every* invariant must be checked explicitly in
application code. That check existed for `add()` but was missing for
`update()`. This was a gap in the in-memory implementation, not a
difference in intended behavior — both repositories are required by
`REPOSITORY_INTERFACE.md` §7 to raise `ConflictError` for the same
category of failure regardless of storage technology.

## The fix

```python
def update(self, patient: Patient) -> Patient:
    if patient.patient_id not in self._store.patients:
        raise NotFoundError(
            f"No patient with id {patient.patient_id!r}",
            aggregate=self.aggregate_name,
        )
    existing_with_phone = self.find_by_phone_number(patient.phone_number)
    if (
        existing_with_phone is not None
        and existing_with_phone.patient_id != patient.patient_id
    ):
        raise ConflictError(
            f"Phone number {patient.phone_number!r} already registered",
            aggregate=self.aggregate_name,
        )
    self._store.patients[patient.patient_id] = patient
    return patient
```

Two properties were required and both are satisfied:

1. **Detect a genuine collision.** If another patient already holds the
   incoming `phone_number`, raise `ConflictError` — matching SQLite's
   `UNIQUE INDEX` behavior on `UPDATE`.
2. **Allow a self-update.** A patient re-saving their own current phone
   number (unchanged, or updated alongside some other field like `name`)
   must not be treated as a conflict. This was verified directly against
   SQLite before writing the fix — SQLite's unique index does not fire
   when a row is "updated" to the value it already holds, since no *other*
   row holds that value. The `existing_with_phone.patient_id !=
   patient.patient_id` exclusion reproduces this exactly: it only rejects
   the update when the phone number belongs to a *different* patient_id.

No new imports were required — `ConflictError` was already imported in
this module. No public interface changed; `PatientRepository.update()`'s
signature and documented exception contract (`ConflictError`,
`NotFoundError`) are unchanged, only now correctly honored.

## Why repository contract parity is now restored

`REPOSITORY_INTERFACE.md` §7 requires that every concrete repository
translate storage-level failures into the same closed error vocabulary,
and `SQLITE_REPOSITORY_DESIGN.md` §14 requires that the same contract-test
suite be "reusable, unchanged, against any future concrete repository."
Before this fix, that guarantee was documented but not actually true for
this one path: a test written only against the in-memory mock (as
recommended for fast Queue Engine testing) could pass a duplicate-phone
scenario that would fail against real SQLite in production — a silent
behavioral drift the Repository Interface pattern exists specifically to
prevent. With the fix, both implementations now reject the same input
with the same exception type for the same reason, and both continue to
accept the same legitimate self-update case.

## Tests that verify the fix

`tests/test_contract_patient_repository.py::test_update_duplicate_phone_number_raises_conflict`,
new in this change:

```python
def test_update_duplicate_phone_number_raises_conflict(uow_factory):
    first = make_patient(phone_number="+8801700000001")
    second = make_patient(phone_number="+8801700000002")
    with uow_factory() as uow:
        uow.patients.add(first)
        uow.patients.add(second)
        uow.commit()

    updated_second = make_patient(
        patient_id=second.patient_id,
        name=second.name,
        phone_number=first.phone_number,
        created_at=second.created_at,
    )
    with uow_factory() as uow:
        with pytest.raises(ConflictError):
            uow.patients.update(updated_second)
```

Because this test is added to the existing contract-test file and uses
the existing `uow_factory` fixture (already parametrized over `sqlite`
and `memory` in `tests/conftest.py`), it runs unchanged against both
concrete repositories — no separate test per implementation was written
or is needed. This is the same mechanism that already runs every other
`PatientRepository` contract test against both implementations.

The pre-existing `test_update_persists_new_values` test (a legitimate
update, including with an unchanged phone number) continues to pass,
confirming the fix does not reject the self-update case.

---

## Validation results

- **Patch verified to apply cleanly** with `git apply --check` against a
  pristine extraction of the originally uploaded repository (no
  conflicts, no fuzz).
- **Baseline (before fix), full suite:** 73 passed.
- **After fix, full suite:** 75 passed (73 original + 2 new — the new
  test runs once per `uow_factory` parametrization: `sqlite` and
  `memory`).
- **No regressions.** Every test that passed before the fix still passes
  after it; no test was modified or removed.
- Verified on a fresh, independent checkout of the original zip with the
  patch applied via `git apply`, not just in the working copy the fix was
  developed in.
