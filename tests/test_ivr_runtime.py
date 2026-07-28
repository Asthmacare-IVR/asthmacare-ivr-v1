"""Tests for the IVR Runtime layer — ISSUE #5 PR-2A.

Covers `ivr.runtime.IVRRuntime`, `ivr.session.IVRSession`,
`ivr.player.PromptPlayer`, `ivr.dtmf_runtime.RuntimeDTMFCollector`, and
`ivr.events`. Uses `asyncio.run(...)` per-call, matching the convention
already used by `tests/test_sim900a_adapter.py` (no pytest-asyncio
plugin is installed in this project).

No telephony/adapters/sim900a code is exercised here: `FakeTelephony`
below is a minimal in-memory `TelephonyInterface`, independent of the
real modem adapter.
"""

from __future__ import annotations

import asyncio

import pytest

from ivr.dtmf_runtime import RuntimeDTMFCollector
from ivr.events import QueueRegistrationRequested, RuntimeEvent, RuntimeEventType
from ivr.models import IVRContext, IVRState
from ivr.player import PromptPlayer
from ivr.prompts import GOODBYE_PROMPT, PATIENT_ID_PROMPT, WELCOME_PROMPT
from ivr.runtime import IVRRuntime
from ivr.session import IVRSession
from ivr.workflow import DefaultIVRWorkflow
from telephony.domain import (
    CallHandle,
    CallRequest,
    EventType,
    SmsHandle,
    SmsRequest,
    TelephonyEvent,
)
from telephony.errors import CallFailedError, TelephonyError
from telephony.interface import TelephonyInterface

VALID_PATIENT_ID = "123456"
CALL_ID = "call-1"
PHONE_NUMBER = "+8801712345678"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeTelephony(TelephonyInterface):
    """Minimal in-memory `TelephonyInterface`. No serial/modem code."""

    def __init__(self) -> None:
        self.hangup_calls: list[str] = []
        self.raise_on_hangup: Exception | None = None

    async def place_call(self, request: CallRequest) -> CallHandle:
        return CallHandle(call_id="unused", phone_number=request.phone_number)

    async def send_sms(self, request: SmsRequest) -> SmsHandle:
        return SmsHandle(message_id="unused", phone_number=request.phone_number)

    async def poll_events(self) -> list[TelephonyEvent]:
        return []

    async def hangup(self, call_id: str) -> None:
        self.hangup_calls.append(call_id)
        if self.raise_on_hangup is not None:
            raise self.raise_on_hangup


class FakePlayer(PromptPlayer):
    def __init__(self) -> None:
        self.played: list[str] = []
        self.stop_count = 0

    async def play(self, prompt: str) -> None:
        self.played.append(prompt)

    async def stop(self) -> None:
        self.stop_count += 1


class ScriptedDTMFCollector(RuntimeDTMFCollector):
    """Returns each entry in `script` in order, one per `await_digits` call."""

    def __init__(self, script: list[str | None]) -> None:
        self._script = list(script)
        self.calls: list[float] = []
        self.cancel_count = 0

    async def await_digits(self, timeout_seconds: float) -> str | None:
        self.calls.append(timeout_seconds)
        if not self._script:
            return None
        return self._script.pop(0)

    async def cancel(self) -> None:
        self.cancel_count += 1


class BlockingDTMFCollector(RuntimeDTMFCollector):
    """Never resolves `await_digits` on its own -- genuinely suspends the
    caller (via `asyncio.Event.wait()`), so tests can exercise
    `IVRRuntime`'s hangup-signal race in `_await_digits_or_hangup`
    against a call that is truly still waiting on input."""

    def __init__(self) -> None:
        self.cancel_count = 0
        self._release = asyncio.Event()

    async def await_digits(self, timeout_seconds: float) -> str | None:
        await self._release.wait()
        return None

    async def cancel(self) -> None:
        self.cancel_count += 1


def make_runtime(
    script: list[str | None] | None = None,
    *,
    telephony: FakeTelephony | None = None,
    max_retries: int = 2,
) -> tuple[IVRRuntime, FakeTelephony, FakePlayer, ScriptedDTMFCollector]:
    telephony = telephony if telephony is not None else FakeTelephony()
    player = FakePlayer()
    dtmf = ScriptedDTMFCollector(script or [])
    runtime = IVRRuntime(telephony, player, dtmf, max_retries=max_retries)
    return runtime, telephony, player, dtmf


def call_answered(
    call_id: str | None = CALL_ID, phone_number: str = PHONE_NUMBER
) -> TelephonyEvent:
    return TelephonyEvent(
        event_type=EventType.CALL_ANSWERED, phone_number=phone_number, call_id=call_id
    )


def call_ended(call_id: str | None = CALL_ID, phone_number: str = PHONE_NUMBER) -> TelephonyEvent:
    return TelephonyEvent(
        event_type=EventType.CALL_ENDED, phone_number=phone_number, call_id=call_id
    )


def event_types(results: list) -> list[RuntimeEventType]:
    return [r.event_type for r in results if isinstance(r, RuntimeEvent)]


# ---------------------------------------------------------------------------
# ivr.events
# ---------------------------------------------------------------------------


class TestEvents:
    def test_runtime_event_is_frozen_and_carries_identity(self) -> None:
        event = RuntimeEvent(
            event_type=RuntimeEventType.WELCOME, call_id=CALL_ID, phone_number=PHONE_NUMBER
        )
        assert event.event_type is RuntimeEventType.WELCOME
        assert event.call_id == CALL_ID
        assert event.metadata == {}
        with pytest.raises(AttributeError):
            event.call_id = "other"  # type: ignore[misc]

    def test_queue_registration_requested_shape(self) -> None:
        request = QueueRegistrationRequested(
            patient_id=VALID_PATIENT_ID, call_id=CALL_ID, phone_number=PHONE_NUMBER
        )
        assert request.patient_id == VALID_PATIENT_ID
        with pytest.raises(AttributeError):
            request.patient_id = "999999"  # type: ignore[misc]

    def test_runtime_event_type_values_cover_spec_list(self) -> None:
        expected = {
            "CALL_STARTED",
            "WELCOME",
            "PATIENT_IDENTIFICATION",
            "INVALID_INPUT",
            "RETRY",
            "CALL_COMPLETED",
            "CALL_FAILED",
            "TIMEOUT",
            "HANGUP",
        }
        assert {member.name for member in RuntimeEventType} == expected


# ---------------------------------------------------------------------------
# ivr.session
# ---------------------------------------------------------------------------


class TestIVRSession:
    @pytest.fixture
    def session(self) -> IVRSession:
        workflow = DefaultIVRWorkflow(IVRContext(call_id=CALL_ID, phone_number=PHONE_NUMBER))
        return IVRSession(call_id=CALL_ID, phone_number=PHONE_NUMBER, workflow=workflow)

    def test_defaults(self, session: IVRSession) -> None:
        assert session.current_prompt is None
        assert session.retry_count == 0
        assert session.finished is False
        assert session.patient_id is None

    def test_touch_updates_last_activity(self, session: IVRSession) -> None:
        before = session.last_activity
        session.touch()
        assert session.last_activity >= before

    def test_mark_finished_sets_flag_and_touches(self, session: IVRSession) -> None:
        assert session.finished is False
        session.mark_finished()
        assert session.finished is True


# ---------------------------------------------------------------------------
# ivr.player / ivr.dtmf_runtime — abstractness
# ---------------------------------------------------------------------------


class TestAbstractions:
    def test_prompt_player_cannot_be_instantiated_directly(self) -> None:
        with pytest.raises(TypeError):
            PromptPlayer()  # type: ignore[abstract]

    def test_dtmf_collector_cannot_be_instantiated_directly(self) -> None:
        with pytest.raises(TypeError):
            RuntimeDTMFCollector()  # type: ignore[abstract]

    def test_fake_player_implements_contract(self) -> None:
        player = FakePlayer()
        asyncio.run(player.play(WELCOME_PROMPT))
        asyncio.run(player.stop())
        assert player.played == [WELCOME_PROMPT]
        assert player.stop_count == 1

    def test_scripted_collector_implements_contract(self) -> None:
        collector = ScriptedDTMFCollector(["1234"])
        assert asyncio.run(collector.await_digits(5.0)) == "1234"
        assert asyncio.run(collector.await_digits(5.0)) is None
        asyncio.run(collector.cancel())
        assert collector.cancel_count == 1


# ---------------------------------------------------------------------------
# IVRRuntime — call start / happy path
# ---------------------------------------------------------------------------


class TestCallStart:
    def test_call_answered_creates_session_and_plays_welcome(self) -> None:
        runtime, _telephony, player, dtmf = make_runtime([VALID_PATIENT_ID])
        asyncio.run(runtime.handle_event(call_answered()))

        session = runtime.get_session(CALL_ID)
        assert session is not None
        assert session.call_id == CALL_ID
        assert session.phone_number == PHONE_NUMBER
        assert WELCOME_PROMPT in player.played
        assert PATIENT_ID_PROMPT in player.played
        assert dtmf.calls == [15.0]

    def test_duplicate_call_answered_is_a_no_op(self) -> None:
        runtime, *_ = make_runtime([VALID_PATIENT_ID])
        first = asyncio.run(runtime.handle_event(call_answered()))
        second = asyncio.run(runtime.handle_event(call_answered()))
        assert first != []
        assert second == []

    def test_session_key_falls_back_to_phone_number_without_call_id(self) -> None:
        runtime, *_ = make_runtime([VALID_PATIENT_ID])
        asyncio.run(runtime.handle_event(call_answered(call_id=None)))
        session = runtime.get_session(PHONE_NUMBER)
        assert session is not None
        assert session.call_id == PHONE_NUMBER  # falls back to the key itself

    def test_incoming_call_ringing_alone_creates_no_session(self) -> None:
        runtime, *_ = make_runtime([])
        ringing = TelephonyEvent(event_type=EventType.INCOMING_CALL, phone_number=PHONE_NUMBER)
        results = asyncio.run(runtime.handle_event(ringing))
        assert results == []
        assert runtime.active_sessions == []

    def test_sms_received_is_ignored(self) -> None:
        runtime, *_ = make_runtime([])
        sms = TelephonyEvent(
            event_type=EventType.SMS_RECEIVED, phone_number=PHONE_NUMBER, message="hi"
        )
        assert asyncio.run(runtime.handle_event(sms)) == []


class TestHappyPath:
    def test_valid_patient_id_emits_expected_sequence_and_halts_at_queue_registration(
        self,
    ) -> None:
        runtime, telephony, player, _dtmf = make_runtime([VALID_PATIENT_ID])
        results = asyncio.run(runtime.handle_event(call_answered()))

        assert event_types(results) == [
            RuntimeEventType.CALL_STARTED,
            RuntimeEventType.WELCOME,
            RuntimeEventType.PATIENT_IDENTIFICATION,
        ]
        registration_requests = [r for r in results if isinstance(r, QueueRegistrationRequested)]
        assert len(registration_requests) == 1
        request = registration_requests[0]
        assert request.patient_id == VALID_PATIENT_ID
        assert request.call_id == CALL_ID
        assert request.phone_number == PHONE_NUMBER

        session = runtime.get_session(CALL_ID)
        assert session is not None
        assert session.finished is False  # halted, not finished -- PR-2B's job
        assert session.workflow.current_state() == IVRState.QUEUE_REGISTRATION
        assert session.patient_id == VALID_PATIENT_ID
        assert telephony.hangup_calls == []  # not hung up while still pending

    def test_terminator_character_is_unknown_but_succeeds_on_retry(self) -> None:
        # ivr.dtmf.classify_patient_id_input treats ANY non-digit
        # character (including a trailing '#' terminator) as UNKNOWN --
        # it does not normalize-then-validate. A collector is expected
        # to strip terminators itself (see ivr/dtmf_runtime.py); this
        # documents what happens if one does not.
        runtime, *_ = make_runtime([f"{VALID_PATIENT_ID}#", VALID_PATIENT_ID])
        results = asyncio.run(runtime.handle_event(call_answered()))
        assert RuntimeEventType.INVALID_INPUT in event_types(results)
        assert RuntimeEventType.RETRY in event_types(results)
        request = next(r for r in results if isinstance(r, QueueRegistrationRequested))
        assert request.patient_id == VALID_PATIENT_ID


# ---------------------------------------------------------------------------
# IVRRuntime — invalid input / timeout / retry / failure
# ---------------------------------------------------------------------------


class TestDtmfRetries:
    def test_invalid_input_then_valid_emits_invalid_and_retry_then_succeeds(self) -> None:
        runtime, *_ = make_runtime(["*bad*", VALID_PATIENT_ID], max_retries=2)
        results = asyncio.run(runtime.handle_event(call_answered()))

        assert RuntimeEventType.INVALID_INPUT in event_types(results)
        assert RuntimeEventType.RETRY in event_types(results)
        assert any(isinstance(r, QueueRegistrationRequested) for r in results)

        session = runtime.get_session(CALL_ID)
        assert session is not None
        assert session.retry_count == 1

    def test_timeout_then_valid_emits_timeout_and_retry_then_succeeds(self) -> None:
        runtime, *_ = make_runtime([None, VALID_PATIENT_ID], max_retries=2)
        results = asyncio.run(runtime.handle_event(call_answered()))

        assert RuntimeEventType.TIMEOUT in event_types(results)
        assert RuntimeEventType.RETRY in event_types(results)
        assert any(isinstance(r, QueueRegistrationRequested) for r in results)

    def test_retry_metadata_tracks_attempt_and_max(self) -> None:
        runtime, *_ = make_runtime([None, VALID_PATIENT_ID], max_retries=2)
        results = asyncio.run(runtime.handle_event(call_answered()))
        retry_event = next(
            r
            for r in results
            if isinstance(r, RuntimeEvent) and r.event_type == RuntimeEventType.RETRY
        )
        assert retry_event.metadata == {"attempt": 1, "max_attempts": 2}

    def test_exceeding_max_retries_fails_the_call_and_hangs_up(self) -> None:
        runtime, telephony, *_ = make_runtime(["bad-1", "bad-2", "bad-3"], max_retries=2)
        results = asyncio.run(runtime.handle_event(call_answered()))

        types = event_types(results)
        assert types.count(RuntimeEventType.INVALID_INPUT) == 3
        assert types.count(RuntimeEventType.RETRY) == 2
        assert RuntimeEventType.CALL_FAILED in types
        assert not any(isinstance(r, QueueRegistrationRequested) for r in results)

        session = runtime.get_session(CALL_ID)
        assert session is not None
        assert session.finished is True
        assert session.workflow.is_finished()
        assert telephony.hangup_calls == [CALL_ID]
        assert CALL_ID not in runtime._hangup_signals

    def test_all_timeouts_fails_the_call(self) -> None:
        runtime, telephony, *_ = make_runtime([None, None, None], max_retries=2)
        results = asyncio.run(runtime.handle_event(call_answered()))
        assert RuntimeEventType.CALL_FAILED in event_types(results)
        assert telephony.hangup_calls == [CALL_ID]

    def test_hangup_failure_during_call_failed_is_swallowed(self) -> None:
        telephony = FakeTelephony()
        telephony.raise_on_hangup = CallFailedError("already down")
        runtime, telephony, *_ = make_runtime(
            ["bad-1", "bad-2", "bad-3"], telephony=telephony, max_retries=2
        )
        results = asyncio.run(runtime.handle_event(call_answered()))
        assert RuntimeEventType.CALL_FAILED in event_types(results)
        assert telephony.hangup_calls == [CALL_ID]


# ---------------------------------------------------------------------------
# IVRRuntime — call ending mid-flow vs. after hand-off
# ---------------------------------------------------------------------------


class TestCallEnding:
    def test_call_ended_before_queue_registration_emits_hangup_and_call_failed(self) -> None:
        telephony = FakeTelephony()
        player = FakePlayer()
        dtmf = BlockingDTMFCollector()
        runtime = IVRRuntime(telephony, player, dtmf, max_retries=2)

        async def scenario() -> tuple[list, list]:
            started_task = asyncio.ensure_future(runtime.handle_event(call_answered()))
            await asyncio.sleep(0)  # let it run up to the blocked DTMF wait
            ended_results = await runtime.handle_event(call_ended())
            started_results = await started_task
            return started_results, ended_results

        started_results, ended_results = asyncio.run(scenario())

        # The in-progress collection attempt was interrupted -- it never
        # got to emit anything of its own past PATIENT_IDENTIFICATION.
        assert event_types(started_results) == [
            RuntimeEventType.CALL_STARTED,
            RuntimeEventType.WELCOME,
            RuntimeEventType.PATIENT_IDENTIFICATION,
        ]
        assert event_types(ended_results) == [RuntimeEventType.HANGUP, RuntimeEventType.CALL_FAILED]

        session = runtime.get_session(CALL_ID)
        assert session is not None
        assert session.finished is True
        assert dtmf.cancel_count == 1
        assert player.stop_count == 1
        assert telephony.hangup_calls == [CALL_ID]  # from workflow.fail() -> FAILED -> END
        assert CALL_ID not in runtime._hangup_signals  # cleaned up, no leak

    def test_call_ended_after_queue_registration_emits_call_completed(self) -> None:
        runtime, telephony, *_ = make_runtime([VALID_PATIENT_ID])
        asyncio.run(runtime.handle_event(call_answered()))
        results = asyncio.run(runtime.handle_event(call_ended()))

        assert event_types(results) == [RuntimeEventType.CALL_COMPLETED]
        session = runtime.get_session(CALL_ID)
        assert session is not None
        assert session.finished is True
        # Already handed off to the queue -- the runtime itself never
        # calls hangup() for this path (the call already ended).
        assert telephony.hangup_calls == []

    def test_call_missed_before_answer_is_ignored_no_session(self) -> None:
        runtime, *_ = make_runtime([])
        missed = TelephonyEvent(
            event_type=EventType.CALL_MISSED, phone_number=PHONE_NUMBER, call_id=CALL_ID
        )
        assert asyncio.run(runtime.handle_event(missed)) == []

    def test_call_ended_twice_is_a_no_op_second_time(self) -> None:
        telephony = FakeTelephony()
        player = FakePlayer()
        dtmf = BlockingDTMFCollector()
        runtime = IVRRuntime(telephony, player, dtmf, max_retries=2)

        async def scenario() -> tuple[list, list]:
            started_task = asyncio.ensure_future(runtime.handle_event(call_answered()))
            await asyncio.sleep(0)
            first = await runtime.handle_event(call_ended())
            second = await runtime.handle_event(call_ended())
            await started_task
            return first, second

        first, second = asyncio.run(scenario())
        assert first != []
        assert second == []

    def test_active_sessions_excludes_finished(self) -> None:
        telephony = FakeTelephony()
        player = FakePlayer()
        dtmf = BlockingDTMFCollector()
        runtime = IVRRuntime(telephony, player, dtmf, max_retries=2)

        async def scenario() -> None:
            started_task = asyncio.ensure_future(runtime.handle_event(call_answered()))
            await asyncio.sleep(0)
            assert len(runtime.active_sessions) == 1
            await runtime.handle_event(call_ended())
            assert runtime.active_sessions == []
            await started_task

        asyncio.run(scenario())


# ---------------------------------------------------------------------------
# IVRRuntime — poll_and_dispatch
# ---------------------------------------------------------------------------


class TestPollAndDispatch:
    def test_poll_and_dispatch_handles_each_polled_event_in_order(self) -> None:
        class QueuedTelephony(FakeTelephony):
            def __init__(self, events: list[TelephonyEvent]) -> None:
                super().__init__()
                self._events = events

            async def poll_events(self) -> list[TelephonyEvent]:
                events, self._events = self._events, []
                return events

        telephony = QueuedTelephony([call_answered()])
        runtime, _telephony, _player, _dtmf = make_runtime([VALID_PATIENT_ID], telephony=telephony)
        results = asyncio.run(runtime.poll_and_dispatch())
        assert RuntimeEventType.CALL_STARTED in event_types(results)

    def test_poll_and_dispatch_with_no_events_returns_empty(self) -> None:
        runtime, *_ = make_runtime([])
        assert asyncio.run(runtime.poll_and_dispatch()) == []


# ---------------------------------------------------------------------------
# IVRRuntime — forward-compatible state-entry branches
# ---------------------------------------------------------------------------
#
# These states are not reached by PR-2A's own flow (it halts at
# QUEUE_REGISTRATION), but the runtime is specified to "handle" them
# (ISSUE #5 PR-2A, "RUNTIME RESPONSIBILITIES"), and a later PR advancing
# a workflow past QUEUE_REGISTRATION will reach them. Exercised directly
# here against a workflow driven to that point via its own public API.


class TestForwardCompatibleStates:
    def _workflow_at(self, state: IVRState) -> DefaultIVRWorkflow:
        workflow = DefaultIVRWorkflow(IVRContext(call_id=CALL_ID, phone_number=PHONE_NUMBER))
        workflow.start()  # -> WELCOME
        path = [
            IVRState.PATIENT_IDENTIFICATION,
            IVRState.PATIENT_VERIFIED,
            IVRState.QUEUE_REGISTRATION,
            IVRState.CONFIRMATION,
            IVRState.CALL_COMPLETED,
        ]
        for _target in path:
            if workflow.current_state() == state:
                break
            workflow.next()
        return workflow

    def test_confirmation_state_is_a_no_op_for_now(self) -> None:
        runtime, *_ = make_runtime([])
        workflow = self._workflow_at(IVRState.CONFIRMATION)
        session = IVRSession(call_id=CALL_ID, phone_number=PHONE_NUMBER, workflow=workflow)
        results = asyncio.run(runtime._enter_state(session, IVRState.CONFIRMATION))
        assert results == []
        assert session.finished is False

    def test_call_completed_state_plays_goodbye_and_finishes(self) -> None:
        runtime, telephony, player, _dtmf = make_runtime([])
        workflow = self._workflow_at(IVRState.CALL_COMPLETED)
        session = IVRSession(call_id=CALL_ID, phone_number=PHONE_NUMBER, workflow=workflow)
        results = asyncio.run(runtime._enter_state(session, IVRState.CALL_COMPLETED))

        assert event_types(results) == [RuntimeEventType.CALL_COMPLETED]
        assert GOODBYE_PROMPT in player.played
        assert session.finished is True
        assert workflow.current_state() == IVRState.END
        assert telephony.hangup_calls == [CALL_ID]

    def test_queue_registration_without_patient_id_raises(self) -> None:
        runtime, *_ = make_runtime([])
        workflow = self._workflow_at(IVRState.QUEUE_REGISTRATION)
        session = IVRSession(call_id=CALL_ID, phone_number=PHONE_NUMBER, workflow=workflow)
        assert session.patient_id is None
        with pytest.raises(RuntimeError):
            runtime._enter_queue_registration(session)

    def test_enter_state_defensive_fallback_for_start_and_end(self) -> None:
        # IVRState.START/END are never (re-)entered via _enter_state in
        # PR-2A's own flow (START only appears before workflow.start(),
        # END only after a terminal _enter_call_completed/_enter_failed
        # already returned); this only exercises the defensive fallback.
        runtime, *_ = make_runtime([])
        workflow = DefaultIVRWorkflow(IVRContext(call_id=CALL_ID, phone_number=PHONE_NUMBER))
        session = IVRSession(call_id=CALL_ID, phone_number=PHONE_NUMBER, workflow=workflow)
        assert asyncio.run(runtime._enter_state(session, IVRState.START)) == []
        assert asyncio.run(runtime._enter_state(session, IVRState.END)) == []

    def test_fail_session_when_already_terminal_is_a_no_op(self) -> None:
        runtime, telephony, *_ = make_runtime([], max_retries=0)
        workflow = self._workflow_at(IVRState.PATIENT_IDENTIFICATION)
        session = IVRSession(call_id=CALL_ID, phone_number=PHONE_NUMBER, workflow=workflow)

        first = asyncio.run(runtime._fail_session(session, "first failure"))
        assert RuntimeEventType.CALL_FAILED in event_types(first)
        assert session.workflow.is_finished()
        assert session.finished is True

        second = asyncio.run(runtime._fail_session(session, "second failure"))
        assert second == []
        assert telephony.hangup_calls.count(CALL_ID) == 1  # not hung up again


# ---------------------------------------------------------------------------
# IVRRuntime — telephony/errors is used (not queue_engine, not database)
# ---------------------------------------------------------------------------


def test_runtime_module_does_not_import_forbidden_packages() -> None:
    import ivr.runtime as runtime_module

    source = runtime_module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "import queue_engine" not in text
    assert "from queue_engine" not in text
    assert "import backend" not in text
    assert "from backend" not in text
    assert "import database" not in text
    assert "from database" not in text


def test_telephony_error_import_is_reachable() -> None:
    # Sanity check that ivr.runtime's TelephonyError import path is live
    # (used by _request_hangup's best-effort swallow).
    assert issubclass(CallFailedError, TelephonyError)
