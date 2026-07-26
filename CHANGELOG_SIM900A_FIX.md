# SIM900A Adapter — Fix Pass Changelog

Scope: `telephony/adapters/sim900a.py` only. No other file was modified.
`tests/test_sim900a_adapter.py` and `tests/sim900a_fake_modem.py` were left
byte-for-byte untouched — verified with `git diff` before packaging.

## Files modified

### `telephony/adapters/sim900a.py`

1. **Removed the literal string `queue_engine`** from two docstrings
   (module docstring, `state` property docstring), reworded to "the Queue
   Engine" — same meaning, no runtime behavior change. This is what made
   `TestArchitectureBoundary::test_adapter_does_not_import_queue_engine`
   fail; the adapter already had zero runtime import of `queue_engine`,
   only the prose mentioned it.

2. **Fixed the unsolicited-event delivery race in `_AtChannel.drain_unsolicited()`.**
   Root cause: the method did a purely non-blocking `queue.get_nowait()`
   loop. If the reader thread was still mid-flight tokenizing bytes that
   had just arrived on the wire (or, in tests, just been injected) at the
   exact moment `poll_events()` was called, `drain_unsolicited()` would
   return before that line had been routed into the queue — the event
   wasn't lost, but it also wasn't delivered on the poll cycle it should
   have been.
   Fix: wait for the **first** line with a short bounded timeout
   (`_UNSOLICITED_DRAIN_GRACE_SECONDS = 0.05s`, new constant) instead of an
   instant non-blocking check; every line after that first one is still
   drained non-blocking, since by then the reader thread has caught up.
   This is a real synchronization fix in the adapter's queue-draining
   logic, not a test change — it closes the race for any caller, not just
   the test suite, and does not touch `_ReaderThread`, `_route_line`, or
   any other routing logic.
   This fixed: `test_connect_event_marks_answered`,
   `test_no_carrier_emits_call_ended`, `test_incoming_call_with_clip`,
   `test_sms_received_cmt`, `test_sms_received_cmti`.

No other lines in the file were touched. Bugs 1–4 (DIALING/CONNECT state,
CALL_ANSWERED direction, poll_events()-after-disconnect(), and the
double-`connect()` reader-thread leak) were already correctly fixed in the
uploaded project and required no further changes — confirmed by the
passing `test_place_call_success`, `test_connect_event_marks_answered`
(direction assertion), `test_disconnect_during_active_call_synthesizes_call_ended`,
and the double-connect teardown path already present in `connect()`.

## Trade-off disclosed

The 50ms grace window in `drain_unsolicited()` only applies when the
unsolicited queue is empty at call time — the common case in a live
polling loop with nothing new to report. It adds up to 50ms of latency to
those "nothing new" calls in exchange for eliminating the race. If this
overhead matters for your polling interval, the constant
`_UNSOLICITED_DRAIN_GRACE_SECONDS` is the single place to tune it.
