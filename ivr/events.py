"""
Internal event definitions for the IVR runtime layer.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import time
from ivr.models import IVRState


@dataclass
class IVREvent:
    """Base class for all IVR runtime events."""
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionStartedEvent(IVREvent):
    """Emitted when a new IVR session begins."""
    session_id: str = ""
    call_id: str = ""
    phone_number: str = ""


@dataclass
class StateTransitionEvent(IVREvent):
    """Emitted when the IVR workflow transitions between states."""
    session_id: str = ""
    from_state: IVRState = IVRState.START
    to_state: IVRState = IVRState.START


@dataclass
class DTMFReceivedEvent(IVREvent):
    """Emitted when a DTMF digit or sequence is received from the caller."""
    session_id: str = ""
    digits: str = ""


@dataclass
class PromptPlayedEvent(IVREvent):
    """Emitted when an audio prompt finishes playing."""
    session_id: str = ""
    prompt_name: str = ""
    interrupted_by: Optional[str] = None


@dataclass
class QueueRegistrationRequestedEvent(IVREvent):
    """Emitted when a caller successfully completes registration and requests queue entry."""
    session_id: str = ""
    call_id: str = ""
    phone_number: str = ""
    patient_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionTerminatedEvent(IVREvent):
    """Emitted when an IVR session ends or disconnects."""
    session_id: str = ""
    reason: str = "completed"