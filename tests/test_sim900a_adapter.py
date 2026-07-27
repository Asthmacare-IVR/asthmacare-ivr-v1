"""Tests for the SIM900A telephony adapter."""

from __future__ import annotations

import asyncio
import importlib
import pkgutil
import threading
from unittest.mock import patch

import pytest

from telephony.adapters.sim900a import (
    Sim900aAdapter,
    _AtChannel,
    _ModemState,
    _SerialTransport,
    _is_error_line,
    _is_terminal_line,
)
from telephony.domain import CallDirection, CallRequest, EventType, SmsRequest
from telephony.errors import (
    CallFailedError,
    InvalidPhoneNumberError,
    SmsFailedError,
    TelephonyUnavailableError,
)
from telephony.interface import TelephonyInterface
from tests.sim900a_fake_modem import FakeSerialPort


@pytest.fixture
def fake_serial() -> FakeSerialPort:
    return FakeSerialPort()


@pytest.fixture
def adapter(fake_serial: FakeSerialPort) -> Sim900aAdapter:
    modem = Sim900aAdapter(port="TEST", baudrate=9600, timeout=1.0)
    with patch("telephony.adapters.sim900a.serial.Serial", return_value=fake_serial):
        modem.connect()
    yield modem
    with patch("telephony.adapters.sim900a.serial.Serial", return_value=fake_serial):
        modem.disconnect()


class TestHelpers:
    def test_terminal_line_detection(self) -> None:
        assert _is_terminal_line("OK")
        assert _is_terminal_line("+CME ERROR: 10")
        assert _is_terminal_line("CONNECT 9600")
        assert not _is_terminal_line("RING")

    def test_error_line_detection(self) -> None:
        assert _is_error_line("ERROR")
        assert _is_error_line("NO CARRIER")
        assert not _is_error_line("OK")

    def test_ucs2_encoding(self) -> None:
        assert _AtChannel._encode_ucs2_hex("hello") == "00680065006C006C006F"
        assert _AtChannel._encode_ucs2_hex("আমি") == "098609AE09BF"


class TestInterfaceCompliance:
    def test_implements_telephony_interface(self) -> None:
        assert issubclass(Sim900aAdapter, TelephonyInterface)
        assert not Sim900aAdapter.__abstractmethods__

    def test_invalid_phone_number_rejected(self, adapter: Sim900aAdapter) -> None:
        with pytest.raises(InvalidPhoneNumberError):
            asyncio.run(adapter.place_call(CallRequest(phone_number="bad")))
        with pytest.raises(InvalidPhoneNumberError):
            asyncio.run(adapter.send_sms(SmsRequest(phone_number="123", message="hi")))


class TestLifecycle:
    def test_connect_initializes_modem(self, fake_serial: FakeSerialPort) -> None:
        adapter = Sim900aAdapter(port="TEST")
        with patch("telephony.adapters.sim900a.serial.Serial", return_value=fake_serial):
            adapter.connect()
        assert adapter.state == _ModemState.IDLE.value
        written = fake_serial.written()
        assert "AT\r\n" in written
        assert "ATE0\r\n" in written
        assert "AT+CPIN?" in written
        assert "AT+CREG?" in written
        assert "AT+CMGF=1" in written

    def test_disconnect_is_idempotent(self, adapter: Sim900aAdapter, fake_serial: FakeSerialPort) -> None:
        with patch("telephony.adapters.sim900a.serial.Serial", return_value=fake_serial):
            adapter.disconnect()
            adapter.disconnect()
        assert adapter.state == _ModemState.DISCONNECTED.value

    def test_explicit_disconnect_blocks_reconnect(self, adapter: Sim900aAdapter) -> None:
        adapter.disconnect()
        with pytest.raises(TelephonyUnavailableError, match="explicitly disconnected"):
            adapter._ensure_connected()

    def test_sim_not_ready_raises(self, fake_serial: FakeSerialPort) -> None:
        fake_serial._sim_ready = False
        adapter = Sim900aAdapter(port="TEST")
        with patch("telephony.adapters.sim900a.serial.Serial", return_value=fake_serial):
            with pytest.raises(TelephonyUnavailableError, match="SIM is not ready"):
                adapter.connect()

    def test_not_registered_raises(self, fake_serial: FakeSerialPort) -> None:
        fake_serial._registered = False
        adapter = Sim900aAdapter(port="TEST")
        with patch("telephony.adapters.sim900a.serial.Serial", return_value=fake_serial):
            with pytest.raises(TelephonyUnavailableError, match="not registered"):
                adapter.connect()

    def test_async_context_manager(self, fake_serial: FakeSerialPort) -> None:
        async def run() -> None:
            async with Sim900aAdapter(port="TEST") as modem:
                assert modem.state == _ModemState.IDLE.value
            assert modem.state == _ModemState.DISCONNECTED.value

        with patch("telephony.adapters.sim900a.serial.Serial", return_value=fake_serial):
            asyncio.run(run())


class TestCalls:
    def test_place_call_success(self, adapter: Sim900aAdapter, fake_serial: FakeSerialPort) -> None:
        handle = asyncio.run(adapter.place_call(CallRequest(phone_number="+8801712345678")))
        assert handle.phone_number == "+8801712345678"
        assert handle.call_id.startswith("sim900a-")
        assert adapter.state == _ModemState.DIALING.value
        assert "ATD+8801712345678;" in fake_serial.written()

    def test_place_call_rejects_second_active_call(self, adapter: Sim900aAdapter) -> None:
        asyncio.run(adapter.place_call(CallRequest(phone_number="+8801712345678")))
        with pytest.raises(CallFailedError, match="already active"):
            asyncio.run(adapter.place_call(CallRequest(phone_number="+8801799999999")))

    def test_connect_event_marks_answered(self, adapter: Sim900aAdapter, fake_serial: FakeSerialPort) -> None:
        handle = asyncio.run(adapter.place_call(CallRequest(phone_number="+8801712345678")))
        fake_serial.inject("CONNECT 9600")
        events = asyncio.run(adapter.poll_events())
        assert len(events) == 1
        assert events[0].event_type == EventType.CALL_ANSWERED
        assert events[0].call_id == handle.call_id
        assert events[0].direction == CallDirection.OUTBOUND
        assert adapter.state == _ModemState.CONNECTED.value

    def test_hangup_clears_active_call(self, adapter: Sim900aAdapter, fake_serial: FakeSerialPort) -> None:
        handle = asyncio.run(adapter.place_call(CallRequest(phone_number="+8801712345678")))
        asyncio.run(adapter.hangup(handle.call_id))
        assert adapter.state == _ModemState.IDLE.value
        assert "ATH\r\n" in fake_serial.written()

    def test_hangup_wrong_call_id_raises(self, adapter: Sim900aAdapter) -> None:
        handle = asyncio.run(adapter.place_call(CallRequest(phone_number="+8801712345678")))
        with pytest.raises(CallFailedError, match="different call"):
            asyncio.run(adapter.hangup("wrong-id"))

    def test_no_carrier_emits_call_ended(self, adapter: Sim900aAdapter, fake_serial: FakeSerialPort) -> None:
        handle = asyncio.run(adapter.place_call(CallRequest(phone_number="+8801712345678")))
        fake_serial.inject("NO CARRIER")
        events = asyncio.run(adapter.poll_events())
        assert events[0].event_type == EventType.CALL_ENDED
        assert events[0].call_id == handle.call_id


class TestSms:
    def test_send_ascii_sms(self, adapter: Sim900aAdapter, fake_serial: FakeSerialPort) -> None:
        handle = asyncio.run(
            adapter.send_sms(SmsRequest(phone_number="+8801712345678", message="Hello"))
        )
        assert handle.message_id == "42"
        assert handle.phone_number == "+8801712345678"
        written = fake_serial.written()
        assert 'AT+CMGS="+8801712345678"' in written
        assert "Hello\x1a" in written

    def test_send_ucs2_sms_for_bengali(self, adapter: Sim900aAdapter, fake_serial: FakeSerialPort) -> None:
        message = "আমি"
        handle = asyncio.run(
            adapter.send_sms(SmsRequest(phone_number="+8801712345678", message=message))
        )
        assert handle.message_id == "42"
        written = fake_serial.written()
        assert 'AT+CSCS="UCS2"' in written
        assert "098609AE09BF\x1a" in written
        assert 'AT+CSCS="GSM"' in written


class TestUnsolicitedEvents:
    def test_incoming_call_with_clip(self, adapter: Sim900aAdapter, fake_serial: FakeSerialPort) -> None:
        fake_serial.inject('+CLIP: "+8801711111111",145', "RING")
        events = asyncio.run(adapter.poll_events())
        incoming = [event for event in events if event.event_type == EventType.INCOMING_CALL]
        assert len(incoming) == 1
        assert incoming[0].phone_number == "+8801711111111"
        assert incoming[0].direction == CallDirection.INBOUND

    def test_sms_received_cmt(self, adapter: Sim900aAdapter, fake_serial: FakeSerialPort) -> None:
        fake_serial.inject('+CMT: "+8801722222222",,"26/07/26,12:00:00+24"', "Test body")
        events = asyncio.run(adapter.poll_events())
        sms = [event for event in events if event.event_type == EventType.SMS_RECEIVED]
        assert len(sms) == 1
        assert sms[0].phone_number == "+8801722222222"
        assert sms[0].message == "Test body"

    def test_sms_received_cmti(self, adapter: Sim900aAdapter, fake_serial: FakeSerialPort) -> None:
        fake_serial.inject('+CMTI: "SM",1')
        events = asyncio.run(adapter.poll_events())
        assert events[0].event_type == EventType.SMS_RECEIVED
        assert events[0].phone_number == "unknown"


class TestReconnection:
    def test_disconnect_during_active_call_synthesizes_call_ended(
        self, adapter: Sim900aAdapter, fake_serial: FakeSerialPort
    ) -> None:
        handle = asyncio.run(adapter.place_call(CallRequest(phone_number="+8801712345678")))
        adapter.disconnect()
        events = adapter._poll_events_sync()
        assert len(events) == 1
        assert events[0].event_type == EventType.CALL_ENDED
        assert events[0].call_id == handle.call_id

    def test_reader_disconnect_triggers_reconnect(self, fake_serial: FakeSerialPort) -> None:
        adapter = Sim900aAdapter(port="TEST", timeout=0.5)
        with patch("telephony.adapters.sim900a.serial.Serial", return_value=fake_serial):
            adapter.connect()
            fake_serial.is_open = False
            adapter._channel.disconnected.set()
            adapter._ready_event.clear()
            fake_serial.is_open = True
            adapter._ensure_connected()
        assert adapter.state == _ModemState.IDLE.value


class TestThreadSafety:
    def test_concurrent_poll_and_place_call(self, adapter: Sim900aAdapter, fake_serial: FakeSerialPort) -> None:
        errors: list[BaseException] = []

        def worker() -> None:
            try:
                for _ in range(5):
                    asyncio.run(adapter.poll_events())
                    fake_serial.inject("RING")
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for thread in threads:
            thread.start()
        handle = asyncio.run(adapter.place_call(CallRequest(phone_number="+8801712345678")))
        for thread in threads:
            thread.join(timeout=5)
        assert not errors
        asyncio.run(adapter.hangup(handle.call_id))


class TestArchitectureBoundary:
    def test_queue_engine_does_not_import_adapters(self) -> None:
        import queue_engine

        for _finder, name, _ispkg in pkgutil.walk_packages(queue_engine.__path__, queue_engine.__name__ + "."):
            module = importlib.import_module(name)
            source = getattr(module, "__file__", "") or ""
            if source.endswith(".py"):
                with open(source, encoding="utf-8") as handle:
                    text = handle.read()
                assert "telephony.adapters" not in text
                assert "from telephony.adapters" not in text

    def test_adapter_does_not_import_queue_engine(self) -> None:
        import telephony.adapters.sim900a as sim900a_module

        source_path = sim900a_module.__file__
        assert source_path is not None
        with open(source_path, encoding="utf-8") as handle:
            text = handle.read()
        assert "queue_engine" not in text
        assert "database" not in text
        assert "backend.api" not in text

    def test_adapter_registered_in_init(self) -> None:
        from telephony.adapters import Sim900aAdapter as exported

        assert exported is Sim900aAdapter
