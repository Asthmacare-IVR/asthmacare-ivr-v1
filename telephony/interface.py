from __future__ import annotations

from abc import ABC, abstractmethod

from .domain import (
    CallHandle,
    CallRequest,
    SmsHandle,
    SmsRequest,
    TelephonyEvent,
)


class TelephonyInterface(ABC):
    """
    Hardware-independent telephony contract.
    """

    @abstractmethod
    async def place_call(
        self,
        request: CallRequest,
    ) -> CallHandle:
        """
        Initiate an outbound call.
        """
        raise NotImplementedError

    @abstractmethod
    async def send_sms(
        self,
        request: SmsRequest,
    ) -> SmsHandle:
        """
        Send an SMS message.
        """
        raise NotImplementedError

    @abstractmethod
    async def poll_events(
        self,
    ) -> list[TelephonyEvent]:
        """
        Return newly observed telephony events.
        """
        raise NotImplementedError

    @abstractmethod
    async def hangup(
        self,
        call_id: str,
    ) -> None:
        """
        End an active call.
        """
        raise NotImplementedError