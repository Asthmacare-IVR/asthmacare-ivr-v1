"""Tests for ivr/ — state machine, default workflow, and DTMF helpers.

ISSUE #5 PR-1. No telephony, queue_engine, or database fixtures are used
here: the IVR package is exercised entirely in isolation.
"""

from __future__ import annotations

import pytest

from ivr import prompts
from ivr.dtmf import classify_patient_id_input, normalize_digits, validate_patient_id
from ivr.exceptions import InvalidTransitionError, WorkflowFinishedError
from ivr.models import DTMFResult, IVRContext, IVRState
from ivr.state_machine import IVRStateMachine
from ivr.workflow import DefaultIVRWorkflow

# The canonical happy path, in order.
HAPPY_PATH = [
    IVRState.START,
    IVRState.WELCOME,
    IVRState.PATIENT_IDENTIFICATION,
    IVRState.PATIENT_VERIFIED,
    IVRState.QUEUE_REGISTRATION,
    IVRState.CONFIRMATION,
    IVRState.CALL_COMPLETED,
    IVRState.END,
]


@pytest.fixture
def sm():
    return IVRStateMachine()


@pytest.fixture
def workflow():
    return DefaultIVRWorkflow(IVRContext(call_id="call-1", phone_number="+15551234567"))


# ---------------------------------------------------------------------------
# IVRStateMachine — pure validation
# ---------------------------------------------------------------------------


class TestStateMachineValidTransitions:
    @pytest.mark.parametrize(
        "current,expected_next",
        list(zip(HAPPY_PATH[:-1], HAPPY_PATH[1:], strict=True)),
    )
    def test_linear_successor(self, sm, current, expected_next):
        assert sm.get_next(current) == expected_next
        sm.assert_valid(current, expected_next)  # does not raise

    def test_failed_successor_is_end(self, sm):
        assert sm.get_next(IVRState.FAILED) == IVRState.END
        sm.assert_valid(IVRState.FAILED, IVRState.END)

    @pytest.mark.parametrize(
        "current",
        [
            IVRState.START,
            IVRState.WELCOME,
            IVRState.PATIENT_IDENTIFICATION,
            IVRState.PATIENT_VERIFIED,
            IVRState.QUEUE_REGISTRATION,
            IVRState.CONFIRMATION,
            IVRState.CALL_COMPLETED,
        ],
    )
    def test_any_active_state_can_fail(self, sm, current):
        assert sm.can_fail(current) is True
        assert IVRState.FAILED in sm.get_allowed_targets(current)
        sm.assert_valid(current, IVRState.FAILED)  # does not raise

    def test_end_has_no_allowed_targets(self, sm):
        assert sm.get_allowed_targets(IVRState.END) == frozenset()

    def test_failed_cannot_fail_again(self, sm):
        assert sm.can_fail(IVRState.FAILED) is False
        assert IVRState.FAILED not in sm.get_allowed_targets(IVRState.FAILED)


class TestStateMachineInvalidTransitions:
    def test_skipping_a_state_is_forbidden(self, sm):
        with pytest.raises(InvalidTransitionError, match="not permitted"):
            sm.assert_valid(IVRState.START, IVRState.PATIENT_IDENTIFICATION)

    def test_backwards_transition_is_forbidden(self, sm):
        with pytest.raises(InvalidTransitionError, match="not permitted"):
            sm.assert_valid(IVRState.CONFIRMATION, IVRState.WELCOME)

    def test_end_to_anything_raises_terminal(self, sm):
        with pytest.raises(InvalidTransitionError, match="terminal"):
            sm.assert_valid(IVRState.END, IVRState.START)

    def test_end_to_itself_raises_terminal(self, sm):
        with pytest.raises(InvalidTransitionError, match="terminal"):
            sm.assert_valid(IVRState.END, IVRState.END)

    def test_is_terminal(self, sm):
        assert sm.is_terminal(IVRState.END) is True
        assert sm.is_terminal(IVRState.FAILED) is False
        assert sm.is_terminal(IVRState.START) is False

    def test_validate_returns_forbidden_string(self, sm):
        assert sm.validate(IVRState.START, IVRState.CONFIRMATION) == "FORBIDDEN"

    def test_validate_returns_already_terminal_string(self, sm):
        assert sm.validate(IVRState.END, IVRState.START) == "ALREADY_TERMINAL"

    def test_validate_returns_allowed_string(self, sm):
        assert sm.validate(IVRState.START, IVRState.WELCOME) == "ALLOWED"


# ---------------------------------------------------------------------------
# DefaultIVRWorkflow
# ---------------------------------------------------------------------------


class TestWorkflowInitialState:
    def test_default_context_starts_at_start(self):
        workflow = DefaultIVRWorkflow()
        assert workflow.current_state() == IVRState.START

    def test_supplied_context_starts_at_start(self, workflow):
        assert workflow.current_state() == IVRState.START

    def test_not_finished_initially(self, workflow):
        assert workflow.is_finished() is False


class TestWorkflowHappyPath:
    def test_start_moves_to_welcome(self, workflow):
        assert workflow.start() == IVRState.WELCOME
        assert workflow.current_state() == IVRState.WELCOME

    def test_every_valid_transition_via_next(self, workflow):
        workflow.start()
        for expected in HAPPY_PATH[2:]:
            assert workflow.next() == expected
            assert workflow.current_state() == expected

    def test_is_finished_false_until_end_reached(self, workflow):
        workflow.start()
        for _ in HAPPY_PATH[2:]:
            assert workflow.is_finished() is False
            workflow.next()
        assert workflow.current_state() == IVRState.END
        assert workflow.is_finished() is True

    def test_full_run_reaches_end_and_finishes(self, workflow):
        workflow.start()
        while not workflow.is_finished():
            workflow.next()
        assert workflow.current_state() == IVRState.END
        assert workflow.is_finished() is True


class TestWorkflowInvalidTransitions:
    def test_next_before_start_raises(self, workflow):
        with pytest.raises(InvalidTransitionError):
            workflow.next()

    def test_start_twice_raises(self, workflow):
        workflow.start()
        with pytest.raises(InvalidTransitionError):
            workflow.start()

    def test_next_after_finished_raises_workflow_finished(self, workflow):
        workflow.start()
        while not workflow.is_finished():
            workflow.next()
        with pytest.raises(WorkflowFinishedError):
            workflow.next()

    def test_start_after_finished_raises_workflow_finished(self, workflow):
        workflow.start()
        while not workflow.is_finished():
            workflow.next()
        with pytest.raises(WorkflowFinishedError):
            workflow.start()


class TestWorkflowFailBranch:
    def test_fail_from_active_state_moves_to_failed(self, workflow):
        workflow.start()
        workflow.next()  # PATIENT_IDENTIFICATION
        assert workflow.fail("max attempts exceeded") == IVRState.FAILED
        assert workflow.current_state() == IVRState.FAILED
        assert workflow.is_finished() is False

    def test_fail_reason_recorded_in_metadata(self, workflow):
        workflow.start()
        workflow.fail("caller hung up")
        assert workflow._context.metadata["failure_reason"] == "caller hung up"

    def test_next_after_fail_reaches_end(self, workflow):
        workflow.start()
        workflow.fail()
        assert workflow.next() == IVRState.END
        assert workflow.is_finished() is True

    def test_fail_twice_raises(self, workflow):
        workflow.start()
        workflow.fail()
        with pytest.raises(InvalidTransitionError):
            workflow.fail()

    def test_fail_after_finished_raises_workflow_finished(self, workflow):
        workflow.start()
        while not workflow.is_finished():
            workflow.next()
        with pytest.raises(WorkflowFinishedError):
            workflow.fail()


class TestWorkflowReset:
    def test_reset_returns_to_start(self, workflow):
        workflow.start()
        workflow.next()
        workflow.reset()
        assert workflow.current_state() == IVRState.START
        assert workflow.is_finished() is False

    def test_reset_clears_attempts(self, workflow):
        workflow.start()
        workflow._context.attempts = 3
        workflow.reset()
        assert workflow._context.attempts == 0

    def test_reset_preserves_call_identity(self, workflow):
        workflow.start()
        workflow.reset()
        assert workflow._context.call_id == "call-1"
        assert workflow._context.phone_number == "+15551234567"

    def test_can_restart_after_reset(self, workflow):
        workflow.start()
        workflow.reset()
        assert workflow.start() == IVRState.WELCOME

    def test_reset_from_end_allows_restart(self, workflow):
        workflow.start()
        while not workflow.is_finished():
            workflow.next()
        workflow.reset()
        assert workflow.current_state() == IVRState.START
        assert workflow.is_finished() is False
        assert workflow.start() == IVRState.WELCOME


class TestWorkflowCurrentState:
    def test_current_state_reflects_context(self, workflow):
        assert workflow.current_state() == workflow._context.current_state
        workflow.start()
        assert workflow.current_state() == workflow._context.current_state


# ---------------------------------------------------------------------------
# dtmf.py helpers
# ---------------------------------------------------------------------------


class TestNormalizeDigits:
    def test_strips_non_digits(self):
        assert normalize_digits("12-34#") == "1234"

    def test_none_returns_empty_string(self):
        assert normalize_digits(None) == ""

    def test_all_digits_unchanged(self):
        assert normalize_digits("123456") == "123456"

    def test_empty_string_returns_empty_string(self):
        assert normalize_digits("") == ""


class TestValidatePatientId:
    def test_valid_length_digits(self):
        assert validate_patient_id("12345") is True

    def test_too_short_is_invalid(self):
        assert validate_patient_id("12") is False

    def test_too_long_is_invalid(self):
        assert validate_patient_id("1234567890123") is False

    def test_empty_is_invalid(self):
        assert validate_patient_id("") is False

    def test_non_digit_characters_are_stripped_before_checking(self):
        assert validate_patient_id("1-2-3-4") is True


class TestPrompts:
    @pytest.mark.parametrize(
        "text",
        [
            prompts.WELCOME_PROMPT,
            prompts.PATIENT_ID_PROMPT,
            prompts.CONFIRMATION_PROMPT,
            prompts.GOODBYE_PROMPT,
        ],
    )
    def test_prompt_is_nonempty_string(self, text):
        assert isinstance(text, str)
        assert text.strip() != ""


class TestClassifyPatientIdInput:
    def test_none_is_timeout(self):
        assert classify_patient_id_input(None) == DTMFResult.TIMEOUT

    def test_valid_digits_is_valid(self):
        assert classify_patient_id_input("123456") == DTMFResult.VALID

    def test_out_of_range_digits_is_invalid(self):
        assert classify_patient_id_input("12") == DTMFResult.INVALID

    def test_empty_string_is_invalid(self):
        assert classify_patient_id_input("") == DTMFResult.INVALID

    def test_mixed_characters_is_unknown(self):
        assert classify_patient_id_input("12*34") == DTMFResult.UNKNOWN
