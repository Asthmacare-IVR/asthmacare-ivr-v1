"""Runtime DTMF collection abstraction — ISSUE #5 PR-2A.

`RuntimeDTMFCollector` is `ivr.runtime.IVRRuntime`'s dependency-injected
input boundary. It is deliberately a separate abstraction from
`ivr.dtmf.DTMFCollector`:

* `ivr.dtmf.DTMFCollector` (ISSUE #5 PR-1) is a `typing.Protocol` sketch
  — `collect(timeout_seconds) -> str | None` — marking where a later PR
  would plug in. It is synchronous and has no cancellation method.
* `RuntimeDTMFCollector` (this PR) is that later PR's actual runtime
  abstraction: an `ABC` the runtime depends on and drives, async (to
  match `telephony.interface.TelephonyInterface`), with an explicit
  `cancel()` so an in-progress collection can be abandoned cleanly when
  a call ends while the runtime is still waiting on input.

No modem or serial I/O is implemented here, or anywhere in this PR.
`telephony.interface.TelephonyInterface` has no DTMF-detection method
and `telephony.domain.EventType` has no DTMF member (see
`telephony/adapters/sim900a.py`'s module docstring, "Known limitations —
DTMF"), so a concrete collector backed by the real SIM900A adapter is
not possible without a `telephony` interface revision — out of scope
here and not attempted. This module defines only the contract the
runtime programs against; the pure validation of whatever digits a
concrete collector eventually returns (`ivr.dtmf.normalize_digits`,
`ivr.dtmf.classify_patient_id_input`) already exists and is reused as-is
by `ivr.runtime`, not duplicated.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class RuntimeDTMFCollector(ABC):
    """Something capable of collecting DTMF digits from an active call."""

    @abstractmethod
    async def await_digits(self, timeout_seconds: float) -> str | None:
        """Wait up to `timeout_seconds` for a complete DTMF entry.

        Returns the raw digits collected, or `None` if `timeout_seconds`
        elapses with no entry completed. A concrete implementation
        should strip any DTMF terminator (e.g. a trailing '#') before
        returning: `ivr.dtmf.classify_patient_id_input` treats *any*
        non-digit character in the raw value as
        `ivr.models.DTMFResult.UNKNOWN` rather than normalizing it away,
        so a terminator left in place causes an otherwise-valid entry to
        be rejected.
        """

    @abstractmethod
    async def cancel(self) -> None:
        """Abandon an in-progress `await_digits` call, if any.

        Must be safe to call when no collection is in progress. The
        runtime calls this when a call ends while waiting on input, so a
        pending collection does not linger past the call it belonged to.
        """
