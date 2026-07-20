from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class EventType(str, Enum):
    INCOMING_CALL = "incoming_call"
    CALL_ANSWERED = "call_answered"
    CALL_MISSED = "call_missed"
    CALL_ENDED = "call_ended"
    SMS_RECEIVED = "sms_received"


class CallDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


@dataclass(frozen=True)
class CallRequest:
    phone_number: str


@dataclass(frozen=True)
class SmsRequest:
    phone_number: str
    message: str


@dataclass(frozen=True)
class CallHandle:
    call_id: str
    phone_number: str


@dataclass(frozen=True)
class SmsHandle:
    message_id: str
    phone_number: str


@dataclass(frozen=True)
class TelephonyEvent:
    event_type: EventType
    phone_number: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    call_id: Optional[str] = None
    message: Optional[str] = None
    direction: Optional[CallDirection] = None