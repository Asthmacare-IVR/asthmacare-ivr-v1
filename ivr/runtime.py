"""
Main IVR runtime engine connecting telephony events, sessions, and workflows.
"""

import logging
from typing import Dict, Callable, Optional, Any
from ivr.session import IVRSession
from ivr.workflow import DefaultIVRWorkflow
from ivr.models import IVRState, DTMFResult
from ivr.player import PromptPlayerInterface
from ivr.dtmf_runtime import DTMFRuntime
from ivr.events import (
    IVREvent,
    SessionStartedEvent,
    StateTransitionEvent,
    DTMFReceivedEvent,
    PromptPlayedEvent,
    QueueRegistrationRequestedEvent,
    SessionTerminatedEvent,
)

logger = logging.getLogger(__name__)


class IVRRuntime:
    """Core runtime engine driving IVR call sessions and workflow state machines."""

    def __init__(
        self,
        telephony_interface,
        prompt_player: PromptPlayerInterface,
        dtmf_runtime: DTMFRuntime,
        workflow: Optional[DefaultIVRWorkflow] = None,
    ):
        """
        Initialize the IVR runtime engine.

        Args:
            telephony_interface: Hardware or mock telephony interface.
            prompt_player: Player implementation for audio prompts.
            dtmf_runtime: DTMF collection runtime.
            workflow: Optional workflow instance (defaults to DefaultIVRWorkflow).
        """
        self.telephony = telephony_interface
        self.player = prompt_player
        self.dtmf = dtmf_runtime
        self.workflow = workflow or DefaultIVRWorkflow()
        self.active_sessions: Dict[str, IVRSession] = {}
        self.event_listeners: list[Callable[[IVREvent], None]] = []

    def register_event_listener(self, listener: Callable[[IVREvent], None]) -> None:
        """Register a callback listener for runtime events."""
        self.event_listeners.append(listener)

    def _emit_event(self, event: IVREvent) -> None:
        """Emit an event to all registered listeners."""
        for listener in self.event_listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error("Error in event listener: %s", e)

    def start_session(self, session_id: str, call_id: str, phone_number: str) -> IVRSession:
        """
        Start a new IVR session for an incoming call.

        Args:
            session_id: Unique session identifier.
            call_id: Call identifier from telephony adapter.
            phone_number: Caller phone number.

        Returns:
            Initialized IVRSession instance.
        """
        workflow = DefaultIVRWorkflow(self.workflow._context if hasattr(self.workflow, "_context") else None)
        workflow.reset()
        session = IVRSession(session_id=session_id, call_id=call_id, phone_number=phone_number, initial_state=workflow.start())
        self.active_sessions[session_id] = session
        
        self._emit_event(SessionStartedEvent(
            session_id=session_id,
            call_id=call_id,
            phone_number=phone_number
        ))
        logger.info("Started IVR session %s for phone number %s", session_id, phone_number)
        return session

    def process_call_step(self, session_id: str) -> bool:
        """
        Process the current state step for an active session.

        Args:
            session_id: The session identifier.

        Returns:
            True if the session remains active, False if terminated.
        """
        session = self.active_sessions.get(session_id)
        if not session or not session.is_active:
            logger.warning("Attempted to process inactive or unknown session: %s", session_id)
            return False

        current_state = session.current_state
        logger.info("Processing session %s at state '%s'", session_id, current_state.value)

        try:
            prompt_name = f"prompt_{current_state.value.lower()}"
            digit = self.player.play_prompt(prompt_name, allow_interruption=True)
            
            if digit:
                self._emit_event(DTMFReceivedEvent(session_id=session_id, digits=digit))
                classification = self.dtmf.classify_and_normalize(digit)
                
                if classification == DTMFResult.VALID:
                    next_state = self.workflow.next() if hasattr(self.workflow, "next") else IVRState.QUEUE_REGISTRATION
                    if next_state != current_state:
                        self._emit_event(StateTransitionEvent(
                            session_id=session_id,
                            from_state=current_state,
                            to_state=next_state
                        ))
                        session.update_state(next_state)
                        
                        if next_state == IVRState.QUEUE_REGISTRATION or (hasattr(self.workflow, "is_finished") and self.workflow.is_finished()):
                            if next_state == IVRState.QUEUE_REGISTRATION:
                                self._emit_event(QueueRegistrationRequestedEvent(
                                    session_id=session_id,
                                    call_id=session.call_id,
                                    phone_number=session.phone_number,
                                    patient_data=session.context.metadata
                                ))
                            session.terminate()
                            self._emit_event(SessionTerminatedEvent(session_id=session_id, reason="completed"))
                            return False
                else:
                    retries = session.increment_retry()
                    if retries > 3:
                        logger.warning("Max retries exceeded for session %s", session_id)
                        session.terminate()
                        self._emit_event(SessionTerminatedEvent(session_id=session_id, reason="max_retries_exceeded"))
                        return False
            else:
                retries = session.increment_retry()
                if retries > 3:
                    session.terminate()
                    self._emit_event(SessionTerminatedEvent(session_id=session_id, reason="timeout"))
                    return False

            return session.is_active
        except Exception as e:
            logger.error("Error processing call step for session %s: %s", session_id, e)
            session.terminate()
            self._emit_event(SessionTerminatedEvent(session_id=session_id, reason="error"))
            return False

    def end_session(self, session_id: str, reason: str = "hangup") -> None:
        """Forcefully end an active session."""
        session = self.active_sessions.get(session_id)
        if session and session.is_active:
            session.terminate()
            self._emit_event(SessionTerminatedEvent(session_id=session_id, reason=reason))
            logger.info("Ended IVR session %s due to: %s", session_id, reason)