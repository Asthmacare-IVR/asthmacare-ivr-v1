"""DTMF input — interfaces and helper validation only.

No modem communication, no SIM900A/telephony code. `DTMFCollector` is a
placeholder Protocol marking the extension point a later PR (DTMF
collection) will implement against a real telephony adapter;
`normalize_digits` / `validate_patient_id` / `classify_patient_id_input`
are pure functions the workflow layer (or that future collector) can
call to interpret raw input.
"""

from __future__ import annotations

from typing import Protocol

from ivr.models import DTMFResult

_MIN_PATIENT_ID_LENGTH = 4
_MAX_PATIENT_ID_LENGTH = 12


class DTMFCollector(Protocol):
    """Future integration point (a later PR): something capable of
    collecting DTMF digits from an active call. Not implemented here —
    no modem/telephony code belongs in this package.
    """

    def collect(self, timeout_seconds: float) -> str | None:
        """Return the digits collected, or None on timeout."""
        ...


def normalize_digits(raw: str | None) -> str:
    """Return only the ASCII digit characters in `raw`, in order.

    Strips whitespace, DTMF terminators (e.g. '#'), and any other
    non-digit characters. Returns "" for None or non-digit-only input.
    """
    if raw is None:
        return ""
    return "".join(ch for ch in raw if ch.isdigit())


def validate_patient_id(digits: str) -> bool:
    """True if `digits` is a plausible patient ID: digits-only (after
    normalization) and within length bounds.

    This is a format check only — it does not confirm the ID exists
    (that requires the database, out of scope for this PR).
    """
    normalized = normalize_digits(digits)
    if not normalized:
        return False
    return _MIN_PATIENT_ID_LENGTH <= len(normalized) <= _MAX_PATIENT_ID_LENGTH


def classify_patient_id_input(raw: str | None) -> DTMFResult:
    """Classify one DTMF attempt at entering a patient ID.

    - None (no input received before the collection window closed) -> TIMEOUT
    - Input containing non-digit characters (e.g. stray '*') -> UNKNOWN
    - All-digit input outside the valid length bounds, or empty -> INVALID
    - All-digit input within bounds -> VALID
    """
    if raw is None:
        return DTMFResult.TIMEOUT
    normalized = normalize_digits(raw)
    if raw != normalized:
        return DTMFResult.UNKNOWN
    if validate_patient_id(normalized):
        return DTMFResult.VALID
    return DTMFResult.INVALID
