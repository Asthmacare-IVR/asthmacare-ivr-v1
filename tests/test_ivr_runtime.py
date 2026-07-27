"""
Unit tests for the IVR runtime layer matching PR-1 codebase.
"""

import pytest
from unittest.mock import MagicMock
from ivr.session import IVRSession
from ivr.player import SIM900APromptPlayer
from ivr.dtmf_runtime import DTMFRuntime
from ivr.runtime import IVRRuntime
from ivr.events import SessionStartedEvent, QueueRegistrationRequestedEvent, SessionTerminatedEvent
from ivr.models import IVRState, DTMFResult
from ivr.dtmf import normalize_digits, validate_patient_id, classify_patient_id_input


def test_ivr_session_lifecycle():
    session = IVRSession(session_id="sess-123", call_id="call-456", phone_number="+8801700000000", initial_state=IVRState.WELCOME)
    assert session.session_id == "sess-123"
    assert session.current_state == IVRState.WELCOME
    assert session.is_active is True

    session.update_state(IVRState.PATIENT_IDENTIFICATION)
    assert session.current_state == IVRState.PATIENT_IDENTIFICATION

    retries = session.increment_retry()
    assert retries == 1
    assert session.get_retry_count() == 1

    session.reset_retry()
    assert session.get_retry_count() == 0

    session.terminate()
    assert session.is_active is False


def test_sim900a_prompt_player_mock():
    mock_telephony = MagicMock()
    mock_telephony.play_audio.return_value = "1"

    player = SIM900APromptPlayer(mock_telephony, prompts_dict={"welcome": "welcome.wav"})
    digit = player.play_prompt("welcome", allow_interruption=True)

    assert digit == "1"
    mock_telephony.play_audio.assert_called_once_with("welcome.wav", interruptible=True)


def test_dtmf_runtime_helpers():
    mock_telephony = MagicMock()
    dtmf_rt = DTMFRuntime(mock_telephony, default_timeout_sec=2.0)
    
    assert normalize_digits(" 1234# ") == "1234"
    assert validate_patient_id("12345") is True
    assert validate_patient_id("123") is False
    assert dtmf_rt.classify_and_normalize("12345") == DTMFResult.VALID


def test_ivr_runtime_session_execution():
    mock_telephony = MagicMock()
    mock_player = MagicMock()
    mock_dtmf = MagicMock()
    mock_workflow = MagicMock()

    mock_player.play_prompt.return_value = "12345"
    mock_dtmf.classify_and_normalize.return_value = DTMFResult.VALID
    mock_workflow.next.return_value = IVRState.QUEUE_REGISTRATION
    mock_workflow.is_finished.return_value = True

    runtime = IVRRuntime(
        telephony_interface=mock_telephony,
        prompt_player=mock_player,
        dtmf_runtime=mock_dtmf,
        workflow=mock_workflow,
    )

    events_captured = []
    runtime.register_event_listener(lambda ev: events_captured.append(ev))

    session = runtime.start_session("sess-999", "call-999", "+8801800000000")
    assert session.session_id in runtime.active_sessions

    active = runtime.process_call_step("sess-999")
    assert active is False

    event_types = [type(e) for e in events_captured]
    assert SessionStartedEvent in event_types
    assert QueueRegistrationRequestedEvent in event_types
    assert SessionTerminatedEvent in event_types