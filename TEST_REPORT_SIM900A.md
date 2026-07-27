# SIM900A Adapter — Test Report (real, executed output)

Command run:
```
python3 -m py_compile telephony/adapters/sim900a.py telephony/adapters/__init__.py \
    tests/test_sim900a_adapter.py tests/sim900a_fake_modem.py
python3 -m pytest tests/test_sim900a_adapter.py -v
```

## Compile check
```
COMPILE OK
```

## Full pytest output (verbatim)
```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- /usr/bin/python3
rootdir: /home/claude/project/AsthmaCare-IVR
configfile: pyproject.toml
collecting ... collected 28 items

tests/test_sim900a_adapter.py::TestHelpers::test_terminal_line_detection PASSED [  3%]
tests/test_sim900a_adapter.py::TestHelpers::test_error_line_detection PASSED [  7%]
tests/test_sim900a_adapter.py::TestHelpers::test_ucs2_encoding PASSED    [ 10%]
tests/test_sim900a_adapter.py::TestInterfaceCompliance::test_implements_telephony_interface PASSED [ 14%]
tests/test_sim900a_adapter.py::TestInterfaceCompliance::test_invalid_phone_number_rejected PASSED [ 17%]
tests/test_sim900a_adapter.py::TestLifecycle::test_connect_initializes_modem PASSED [ 21%]
tests/test_sim900a_adapter.py::TestLifecycle::test_disconnect_is_idempotent PASSED [ 25%]
tests/test_sim900a_adapter.py::TestLifecycle::test_explicit_disconnect_blocks_reconnect PASSED [ 28%]
tests/test_sim900a_adapter.py::TestLifecycle::test_sim_not_ready_raises PASSED [ 32%]
tests/test_sim900a_adapter.py::TestLifecycle::test_not_registered_raises PASSED [ 35%]
tests/test_sim900a_adapter.py::TestLifecycle::test_async_context_manager PASSED [ 39%]
tests/test_sim900a_adapter.py::TestCalls::test_place_call_success PASSED [ 42%]
tests/test_sim900a_adapter.py::TestCalls::test_place_call_rejects_second_active_call PASSED [ 46%]
tests/test_sim900a_adapter.py::TestCalls::test_connect_event_marks_answered PASSED [ 50%]
tests/test_sim900a_adapter.py::TestCalls::test_hangup_clears_active_call PASSED [ 53%]
tests/test_sim900a_adapter.py::TestCalls::test_hangup_wrong_call_id_raises PASSED [ 57%]
tests/test_sim900a_adapter.py::TestCalls::test_no_carrier_emits_call_ended PASSED [ 60%]
tests/test_sim900a_adapter.py::TestSms::test_send_ascii_sms PASSED       [ 64%]
tests/test_sim900a_adapter.py::TestSms::test_send_ucs2_sms_for_bengali PASSED [ 67%]
tests/test_sim900a_adapter.py::TestUnsolicitedEvents::test_incoming_call_with_clip PASSED [ 71%]
tests/test_sim900a_adapter.py::TestUnsolicitedEvents::test_sms_received_cmt PASSED [ 75%]
tests/test_sim900a_adapter.py::TestUnsolicitedEvents::test_sms_received_cmti PASSED [ 78%]
tests/test_sim900a_adapter.py::TestReconnection::test_disconnect_during_active_call_synthesizes_call_ended PASSED [ 82%]
tests/test_sim900a_adapter.py::TestReconnection::test_reader_disconnect_triggers_reconnect PASSED [ 85%]
tests/test_sim900a_adapter.py::TestThreadSafety::test_concurrent_poll_and_place_call PASSED [ 89%]
tests/test_sim900a_adapter.py::TestArchitectureBoundary::test_queue_engine_does_not_import_adapters PASSED [ 92%]
tests/test_sim900a_adapter.py::TestArchitectureBoundary::test_adapter_does_not_import_queue_engine PASSED [ 96%]
tests/test_sim900a_adapter.py::TestArchitectureBoundary::test_adapter_registered_in_init PASSED [100%]

=============================== warnings summary ===============================
tests/test_sim900a_adapter.py: 24 warnings
  <string>:5: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 28 passed, 24 warnings in 6.47s ========================
```

## Result
**28 passed, 0 failed.**

## Stability check
Re-ran the full suite 3 additional consecutive times (no code changes between
runs) to confirm the fix to `drain_unsolicited()` actually removed the race
rather than getting lucky once:

```
Run 1: 28 passed
Run 2: 28 passed
Run 3: 28 passed
```

## Note on the DeprecationWarning
`datetime.datetime.utcnow()` in `telephony/domain.py`'s `TelephonyEvent`
default factory is deprecated in Python 3.12+. It does not fail any test
and was out of scope for this bug list (it's in `domain.py`, not the
adapter), so it was left as-is rather than making an unrequested change.
