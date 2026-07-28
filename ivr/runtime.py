"""IVR Runtime — ISSUE #5 PR-2A.

Connects `telephony.interface.TelephonyInterface` to
`ivr.workflow.DefaultIVRWorkflow`: `IVRRuntime` receives
`telephony.domain.TelephonyEvent` objects, creates and drives one
`ivr.session.IVRSession` per active call, requests prompt playback
(`ivr.player.PromptPlayer`) and DTMF collection
(`ivr.dtmf_runtime.RuntimeDTMFCollector`), and reports what happened as
`ivr.events.RuntimeEvent` / `ivr.events.QueueRegistrationRequested`
objects.

Explicitly out of scope here (ISSUE #5 PR-2A): Queue Engine registration
(`queue_engine` is never imported — see `ivr/events.py`), backend
persistence, and database schema changes. A call's workflow halts at
`ivr.models.IVRState.QUEUE_REGISTRATION`; advancing past it is PR-2B's
job.

Event mapping
-------------
`telephony.domain.EventType` and `ivr.models.IVRState` are both narrower
than the nine runtime events this class is responsible for (see
ISSUE #5 PR-2A, "RUNTIME RESPONSIBILITIES"), so the mapping between them
is this runtime's own design decision, not a 1:1 rename:

* CALL_STARTED — a session is created (on `EventType.CALL_ANSWERED` for
  a call not already tracked).
* WELCOME / PATIENT_IDENTIFICATION — fired as each prompt is played.
* INVALID_INPUT / TIMEOUT — fired per bad DTMF attempt (classified
  INVALID/UNKNOWN, or no entry within the collection window).
* RETRY — fired when a bad/timed-out attempt still has retries left.
* CALL_FAILED — fired whenever `DefaultIVRWorkflow.fail()` succeeds,
  regardless of cause (retries exhausted, or an early hangup).
* HANGUP — fired specifically when telephony reports the call ending
  *before* the runtime reached QUEUE_REGISTRATION (the caller dropped
  off mid-flow) — distinct from CALL_FAILED, which describes the
  resulting workflow outcome, not the telephony-level cause.
* CALL_COMPLETED — fired when telephony reports the call ending *after*
  the runtime already reached QUEUE_REGISTRATION (its work for this call
  is done), or if a future PR advances the workflow all the way to the
  literal `IVRState.CALL_COMPLETED`.

Concurrency model
------------------
`IVRRuntime` spawns no threads and keeps no persistent/detached asyncio
task of its own ("no hidden background workers") — it is purely
reactive. The expected driver is an external loop calling
`poll_and_dispatch()` (which calls `TelephonyInterface.poll_events()`
and then `handle_event()` once per event, in order) or feeding
`handle_event()` directly; running several calls concurrently (e.g. via
`asyncio.gather`/`create_task` per call) is that external driver's
choice, not something this class does on its own.

One thing does need to interrupt an in-progress `handle_event()` call
for the *same* call, though: a `TelephonyEvent` reporting the call ended
while `_collect_patient_id` is still awaiting DTMF input. Rather than a
lock (which would simply block the ending call's event until the
collection wait finished on its own — the opposite of "handle a
hangup"), each call gets one `asyncio.Event` ("hangup signal") in
`_hangup_signals`, keyed by `call_id`. `_collect_patient_id` races
`RuntimeDTMFCollector.await_digits()` against that signal; whichever
call to `handle_event()` observes `EventType.CALL_ENDED`/`CALL_MISSED`
for that call sets it, so a concurrently-running collection wait for the
same call unblocks immediately instead of waiting out its full timeout.
This is two short-lived, immediately-awaited tasks per collection
attempt (a standard "race two awaitables" pattern), not a persistent
background worker.

No global mutable state, no singleton: all session state lives in one
`IVRRuntime` instance's `_sessions` (and `_hangup_signals`) dicts,
scoped to that instance.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Final

from ivr.dtmf import classify_patient_id_input, normalize_digits
from ivr.dtmf_runtime import RuntimeDTMFCollector
from ivr.events import QueueRegistrationRequested, RuntimeEvent, RuntimeEventType
from ivr.exceptions import InvalidTransitionError, WorkflowFinishedError
from ivr.interface import IVRWorkflow
from ivr.models import DTMFResult, IVRContext, IVRState
from ivr.player import PromptPlayer
from ivr.prompts import GOODBYE_PROMPT, PATIENT_ID_PROMPT, WELCOME_PROMPT
from ivr.session import IVRSession
from ivr.workflow import DefaultIVRWorkflow
from telephony.domain import EventType, TelephonyEvent
from telephony.errors import TelephonyError
from telephony.interface import TelephonyInterface

_DEFAULT_DTMF_TIMEOUT_SECONDS: Final[float] = 15.0
_DEFAULT_MAX_RETRIES: Final[int] = 2

# Telephony events that mean "this call is over", one way or another.
_CALL_ENDING_EVENT_TYPES: Final[frozenset[EventType]] = frozenset(
    {EventType.CALL_ENDED, EventType.CALL_MISSED}
)

# What a runtime event, or the one queue-registration signal, can be.
RuntimeOutcome = RuntimeEvent | QueueRegistrationRequested

WorkflowFactory = Callable[[IVRContext], IVRWorkflow]


def _default_workflow_factory(context: IVRContext) -> IVRWorkflow:
    return DefaultIVRWorkflow(context)


class IVRRuntime:
    """Drives one `ivr.session.IVRSession` per active call from
    `telephony.domain.TelephonyEvent` objects. See module docstring for
    the full event-mapping and concurrency model."""

    def __init__(
        self,
        telephony: TelephonyInterface,
        player: PromptPlayer,
        dtmf_collector: RuntimeDTMFCollector,
        *,
        workflow_factory: WorkflowFactory = _default_workflow_factory,
        dtmf_timeout_seconds: float = _DEFAULT_DTMF_TIMEOUT_SECONDS,
        max_retries: int = _DEFAULT_MAX_RETRIES,
    ) -> None:
        self._telephony = telephony
        self._player = player
        self._dtmf = dtmf_collector
        self._workflow_factory = workflow_factory
        self._dtmf_timeout_seconds = dtmf_timeout_seconds
        self._max_retries = max_retries

        self._sessions: dict[str, IVRSession] = {}
        # One asyncio.Event per in-flight call, used only to let a
        # CALL_ENDED/CALL_MISSED TelephonyEvent interrupt a concurrently
        # running DTMF collection wait for the same call. See the module
        # docstring, "Concurrency model".
        self._hangup_signals: dict[str, asyncio.Event] = {}

    # -- introspection -------------------------------------------------

    def get_session(self, key: str) -> IVRSession | None:
        """Look up a session by its `call_id` (or phone-number fallback
        key — see `_session_key`)."""
        return self._sessions.get(key)

    @property
    def active_sessions(self) -> list[IVRSession]:
        """Sessions that have not yet finished."""
        return [session for session in self._sessions.values() if not session.finished]

    # -- driving ---------------------------------------------------------

    async def poll_and_dispatch(self) -> list[RuntimeOutcome]:
        """Poll telephony once and handle every event it returns, in order."""
        events = await self._telephony.poll_events()
        results: list[RuntimeOutcome] = []
        for event in events:
            results.extend(await self.handle_event(event))
        return results

    async def handle_event(self, event: TelephonyEvent) -> list[RuntimeOutcome]:
        """Handle one `TelephonyEvent`, driving its call's session forward."""
        key = self._session_key(event)
        if event.event_type == EventType.CALL_ANSWERED:
            return await self._handle_call_answered(key, event)
        if event.event_type in _CALL_ENDING_EVENT_TYPES:
            return await self._handle_call_ended(key, event)
        # EventType.INCOMING_CALL (ringing only) and SMS_RECEIVED carry
        # nothing this runtime acts on in PR-2A scope.
        return []

    # -- call start --------------------------------------------------------

    async def _handle_call_answered(self, key: str, event: TelephonyEvent) -> list[RuntimeOutcome]:
        if key in self._sessions:
            # Already tracking this call -- CALL_ANSWERED is a one-time
            # start trigger, so a duplicate/late poll result is a no-op.
            return []

        call_id = event.call_id or key
        context = IVRContext(call_id=call_id, phone_number=event.phone_number)
        session = IVRSession(
            call_id=call_id,
            phone_number=event.phone_number,
            workflow=self._workflow_factory(context),
        )
        self._sessions[key] = session

        results: list[RuntimeOutcome] = [self._emit(session, RuntimeEventType.CALL_STARTED)]

        session.workflow.start()  # START -> WELCOME
        results.extend(await self._enter_state(session, session.workflow.current_state()))
        return results

    # -- state-entry reactions ----------------------------------------------

    async def _enter_state(self, session: IVRSession, state: IVRState) -> list[RuntimeOutcome]:
        """React to `session.workflow` having just arrived at `state`.

        Recurses along the linear happy path for states that have
        nothing to wait on before moving further; returns/stops at
        states that do (or that end this PR's scope).
        """
        if state == IVRState.WELCOME:
            return await self._enter_welcome(session)
        if state == IVRState.PATIENT_IDENTIFICATION:
            return await self._enter_patient_identification(session)
        if state == IVRState.PATIENT_VERIFIED:
            return await self._enter_patient_verified(session)
        if state == IVRState.QUEUE_REGISTRATION:
            return self._enter_queue_registration(session)
        if state == IVRState.CONFIRMATION:
            # Reachable only once a later PR (Queue Engine integration)
            # advances a call past QUEUE_REGISTRATION; PR-2A never
            # drives here on its own.
            return []
        if state == IVRState.CALL_COMPLETED:
            return await self._enter_call_completed(session)
        if state == IVRState.FAILED:
            return await self._enter_failed(session)
        return []

    async def _enter_welcome(self, session: IVRSession) -> list[RuntimeOutcome]:
        session.current_prompt = WELCOME_PROMPT
        session.touch()
        await self._player.play(WELCOME_PROMPT)
        results: list[RuntimeOutcome] = [self._emit(session, RuntimeEventType.WELCOME)]
        session.workflow.next()  # WELCOME -> PATIENT_IDENTIFICATION
        results.extend(await self._enter_state(session, session.workflow.current_state()))
        return results

    async def _enter_patient_identification(self, session: IVRSession) -> list[RuntimeOutcome]:
        session.current_prompt = PATIENT_ID_PROMPT
        session.touch()
        await self._player.play(PATIENT_ID_PROMPT)
        results: list[RuntimeOutcome] = [
            self._emit(session, RuntimeEventType.PATIENT_IDENTIFICATION)
        ]
        results.extend(await self._collect_patient_id(session))
        return results

    async def _enter_patient_verified(self, session: IVRSession) -> list[RuntimeOutcome]:
        # No caller-facing prompt for PATIENT_VERIFIED -- it is a pure
        # pass-through state on the happy path (docs/IVR_STATE_MACHINE.md).
        session.workflow.next()  # PATIENT_VERIFIED -> QUEUE_REGISTRATION
        return await self._enter_state(session, session.workflow.current_state())

    def _enter_queue_registration(self, session: IVRSession) -> list[RuntimeOutcome]:
        # ISSUE #5 PR-2A boundary: emit the request and stop. No
        # queue_engine import, no registration, no further workflow
        # advancement here -- PR-2B picks up from QUEUE_REGISTRATION.
        if session.patient_id is None:
            raise RuntimeError(
                "Reached QUEUE_REGISTRATION without a validated patient_id; "
                "this indicates an internal runtime invariant was violated."
            )
        return [
            QueueRegistrationRequested(
                patient_id=session.patient_id,
                call_id=session.call_id,
                phone_number=session.phone_number,
            )
        ]

    async def _enter_call_completed(self, session: IVRSession) -> list[RuntimeOutcome]:
        session.current_prompt = GOODBYE_PROMPT
        await self._player.play(GOODBYE_PROMPT)
        results: list[RuntimeOutcome] = [self._emit(session, RuntimeEventType.CALL_COMPLETED)]
        session.workflow.next()  # CALL_COMPLETED -> END
        session.mark_finished()
        self._clear_hangup_signal(session)
        await self._request_hangup(session)
        return results

    async def _enter_failed(self, session: IVRSession) -> list[RuntimeOutcome]:
        results: list[RuntimeOutcome] = [self._emit(session, RuntimeEventType.CALL_FAILED)]
        session.workflow.next()  # FAILED -> END
        session.mark_finished()
        self._clear_hangup_signal(session)
        await self._request_hangup(session)
        return results

    # -- DTMF collection -----------------------------------------------------

    async def _collect_patient_id(self, session: IVRSession) -> list[RuntimeOutcome]:
        results: list[RuntimeOutcome] = []
        while True:
            raw, hung_up = await self._await_digits_or_hangup(session)
            if hung_up:
                # A concurrent handle_event() call already observed
                # CALL_ENDED/CALL_MISSED for this call and is handling
                # (or has handled) HANGUP/CALL_FAILED itself -- this
                # collection attempt simply stops.
                return results
            session.touch()
            classification = classify_patient_id_input(raw)

            if classification == DTMFResult.VALID:
                session.patient_id = normalize_digits(raw)
                session.workflow.next()  # PATIENT_IDENTIFICATION -> PATIENT_VERIFIED
                results.extend(await self._enter_state(session, session.workflow.current_state()))
                return results

            if classification == DTMFResult.TIMEOUT:
                results.append(self._emit(session, RuntimeEventType.TIMEOUT))
            else:  # DTMFResult.INVALID or DTMFResult.UNKNOWN
                results.append(self._emit(session, RuntimeEventType.INVALID_INPUT))

            session.retry_count += 1
            if session.retry_count > self._max_retries:
                results.extend(
                    await self._fail_session(
                        session, "patient ID not confirmed after maximum retry attempts"
                    )
                )
                return results

            results.append(
                self._emit(
                    session,
                    RuntimeEventType.RETRY,
                    attempt=session.retry_count,
                    max_attempts=self._max_retries,
                )
            )
            session.current_prompt = PATIENT_ID_PROMPT
            await self._player.play(PATIENT_ID_PROMPT)

    async def _await_digits_or_hangup(self, session: IVRSession) -> tuple[str | None, bool]:
        """Race `RuntimeDTMFCollector.await_digits()` against this call's
        hangup signal. Returns `(digits, hung_up)`: `hung_up` is True iff
        the call ended before digits were collected (in which case
        `digits` is always `None`)."""
        hangup_event = self._hangup_event_for(session)
        digits_task = asyncio.ensure_future(self._dtmf.await_digits(self._dtmf_timeout_seconds))
        hangup_task = asyncio.ensure_future(hangup_event.wait())
        done, pending = await asyncio.wait(
            {digits_task, hangup_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        if hangup_task in done:
            return None, True
        return digits_task.result(), False

    def _hangup_event_for(self, session: IVRSession) -> asyncio.Event:
        return self._hangup_signals.setdefault(session.call_id, asyncio.Event())

    def _clear_hangup_signal(self, session: IVRSession) -> None:
        self._hangup_signals.pop(session.call_id, None)

    # -- call end --------------------------------------------------------

    async def _handle_call_ended(self, key: str, event: TelephonyEvent) -> list[RuntimeOutcome]:
        session = self._sessions.get(key)
        if session is None or session.finished:
            return []

        session.touch()
        # Set first: unblocks any concurrently-running _collect_patient_id
        # for this call immediately, before the (possibly slower) best-
        # effort adapter/player cleanup below even starts.
        self._hangup_event_for(session).set()
        await self._dtmf.cancel()
        await self._player.stop()

        if session.workflow.current_state() == IVRState.QUEUE_REGISTRATION:
            # The runtime had already handed off registration before the
            # line dropped -- a graceful end from this runtime's point of
            # view, not a failure.
            session.mark_finished()
            self._clear_hangup_signal(session)
            return [self._emit(session, RuntimeEventType.CALL_COMPLETED)]

        results: list[RuntimeOutcome] = [self._emit(session, RuntimeEventType.HANGUP)]
        results.extend(await self._fail_session(session, "call ended before completion"))
        return results

    async def _fail_session(self, session: IVRSession, reason: str) -> list[RuntimeOutcome]:
        try:
            session.workflow.fail(reason)  # -> FAILED
        except (InvalidTransitionError, WorkflowFinishedError):
            # Already terminal, or FAILED is unreachable from here (e.g.
            # a second failure signal for the same call) -- nothing
            # further to do beyond making sure it is marked finished.
            session.mark_finished()
            return []
        return await self._enter_state(session, session.workflow.current_state())

    async def _request_hangup(self, session: IVRSession) -> None:
        try:
            await self._telephony.hangup(session.call_id)
        except TelephonyError:
            # Best-effort: the call may already be down (that is often
            # exactly why we are here), so a hangup failure at this point
            # is not itself a runtime error.
            pass

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _session_key(event: TelephonyEvent) -> str:
        # `TelephonyEvent.call_id` is optional (e.g. a bare inbound RING
        # from `telephony/adapters/sim900a.py` carries none); fall back
        # to phone_number so the call can still be tracked as one session.
        return event.call_id or event.phone_number

    @staticmethod
    def _emit(
        session: IVRSession, event_type: RuntimeEventType, **metadata: object
    ) -> RuntimeEvent:
        return RuntimeEvent(
            event_type=event_type,
            call_id=session.call_id,
            phone_number=session.phone_number,
            metadata=metadata,
        )
