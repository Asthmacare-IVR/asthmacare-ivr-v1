"""SIM900A GSM/GPRS modem adapter.

Implements ``telephony.interface.TelephonyInterface`` for a SIM900A modem
reachable over a serial (UART/USB) connection, using standard AT commands.

Dependency scope (per ``SYSTEM_ARCHITECTURE.md`` Section 4): this module
depends only on ``telephony.interface``, ``telephony.domain``,
``telephony.errors``, the standard library, and ``pyserial``. It is never
imported by the Queue Engine directly -- only through the
``TelephonyInterface`` contract.

Concurrency model
------------------
A single background reader thread (``_ReaderThread``) owns all reads from
the serial port. It tokenizes the raw byte stream into modem response lines
and the SMS ``>`` prompt, and routes each token, under ``_AtChannel``'s
``_route_lock``, to one of two thread-safe queues:

* the *command* queue, while a command is in flight (``_command_active``),
  so the thread waiting on that command sees every line the modem produces
  while it is pending -- including a final result code such as
  ``BUSY``/``NO CARRIER`` arriving instead of ``OK``;
* the *unsolicited* queue otherwise, for events the modem raises on its own
  (incoming ``RING``, an SMS notification, a call dropped after connecting,
  and so on).

The flag flip (``_begin_command``/``_end_command``) and the read-and-route
decision share the same lock, so a line is always classified atomically
with respect to command boundaries -- there is no window in which the
router can observe a torn state.

``poll_events()`` drains only the unsolicited queue (plus any adapter-
generated synthetic events, see "Reconnection" below), so a real event is
enqueued exactly once and never lost between polls, regardless of how the
public async methods happen to interleave.

Modem readiness and reconnection
---------------------------------
``_ready_event`` is the single source of truth for "the modem is open,
initialized, and safe to command." It is set only after a full successful
``connect()`` or reconnect cycle, and cleared at the start of any teardown.
Every public operation calls ``_ensure_connected()`` first, which either
observes readiness and returns immediately, or serializes on
``_lifecycle_lock`` to run a bounded reconnect-and-reinitialize sequence.
This closes the window where one thread could start a reconnect while
another, having checked readiness a moment earlier, sends a command to a
modem that is mid-initialization.

If a call was active when the connection was lost, that information would
otherwise vanish silently (the interface has no "connection lost" event).
Instead, ``_teardown_locked`` synthesizes a ``CALL_ENDED`` event for the
lost call, which ``poll_events()`` surfaces on the next poll -- so the
Queue Engine is told the call ended rather than being left believing it is
still connected.

Known limitations (intentional -- see ``telephony/README.md`` and
``SYSTEM_ARCHITECTURE.md`` Section 3.3 on interface scope)
-----------------------------------------------------------
* **DTMF.** ``TelephonyInterface`` has no method to enable DTMF detection
  and ``domain.EventType`` has no DTMF member, so there is no public
  surface to deliver a DTMF digit through. This adapter therefore does not
  send ``AT+DDET`` and implements no DTMF parsing: code that decodes
  ``+DTMF:`` unsolicited results would have no caller-visible effect and
  would be dead code by construction. Supporting DTMF requires an interface
  revision (a new abstract method and/or ``EventType`` member), which is
  out of scope for this change under the frozen "do not modify the
  interface" constraint. If a future revision adds such a method, the
  reader-thread/queue architecture above already generalizes to a third
  queue for DTMF tokens without changing the transport or command channel.
* **Callbacks.** ``TelephonyInterface`` defines a pull model
  (``poll_events()``) with no callback-registration method. Internally,
  events already flow through a push-style pipeline (the reader thread
  pushes onto a queue as soon as a line arrives); ``poll_events()`` simply
  drains what has accumulated. That internal push mechanism is not
  exposed publicly -- doing so would require a new abstract method on the
  interface, which is out of scope here. Public behavior remains
  polling-only.

Character-set handling for SMS
-------------------------------
``domain.SmsRequest.message`` is an arbitrary ``str`` and this deployment's
patient-facing text is frequently Bengali. A SIM900A in the default "GSM"
character set only supports the GSM 7-bit alphabet; writing UTF-8 bytes
directly for non-ASCII text produces corrupted messages on the handset.
``_AtChannel.send_sms`` therefore detects non-ASCII payloads and briefly
switches the modem to UCS2 mode (``AT+CSCS="UCS2"``) for that single send,
transmitting the message as uppercase-hex-encoded UTF-16BE text, then
restores "GSM" mode -- entirely inside the existing ``AT+CMGS`` flow, with
no change to ``send_sms``'s signature or return value.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import queue
import re
import threading
import time
import uuid
from typing import Callable, Final, Optional

import serial
from serial import SerialException

from ..domain import (
    CallDirection,
    CallHandle,
    CallRequest,
    EventType,
    SmsHandle,
    SmsRequest,
    TelephonyEvent,
)
from ..errors import (
    CallFailedError,
    InvalidPhoneNumberError,
    SmsFailedError,
    TelephonyError,
    TelephonyUnavailableError,
)
from ..interface import TelephonyInterface

logger = logging.getLogger(__name__)

# E.164-ish: optional leading '+', 7-15 digits. Deliberately permissive since
# BUSINESS_RULES.md and QUEUE_RULES.md leave exact numbering-plan validation
# unspecified; this is adapter-local input hygiene, not a business rule.
_PHONE_NUMBER_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\+?[0-9]{7,15}$")

_DEFAULT_COMMAND_TIMEOUT: Final[float] = 5.0
_CALL_SETUP_TIMEOUT: Final[float] = 10.0
_SMS_SEND_TIMEOUT: Final[float] = 15.0
_CTRL_Z: Final[str] = "\x1a"
_SMS_PROMPT: Final[str] = ">"

# Low-level serial read timeout: how long a single blocking read() waits
# before returning control to the reader-thread loop (so it can notice a
# stop request promptly). This is independent of, and much shorter than,
# any AT-command-level timeout below.
_SERIAL_READ_POLL_TIMEOUT: Final[float] = 0.2

# Safety cap on an unterminated line buffer: if this many bytes accumulate
# with no newline and no SMS prompt, the stream is treated as corrupted
# noise and discarded rather than growing without bound.
_MAX_LINE_BUFFER_BYTES: Final[int] = 4096

# Diagnostic-only high-water mark for the unsolicited-event queue; crossing
# it means poll_events() is not being called often enough.
_UNSOLICITED_QUEUE_WARN_THRESHOLD: Final[int] = 500

# drain_unsolicited() grace window: bytes can land on the wire and be
# mid-flight through the reader thread's tokenizer at the exact moment
# poll_events() is called. An instant, purely non-blocking drain has a
# genuine race against that in-flight routing and can silently skip an
# event that is queued microseconds later. Waiting up to this long for the
# *first* line (only when the queue is empty) closes that window; once at
# least one line has arrived, the rest of the drain stays non-blocking.
_UNSOLICITED_DRAIN_GRACE_SECONDS: Final[float] = 0.05

_RECONNECT_ATTEMPTS: Final[int] = 3
_RECONNECT_BACKOFF_SECONDS: Final[float] = 1.0

# How often an in-flight command's wait loop re-checks `disconnected` instead
# of blocking for the full remaining command timeout. Without this, a lost
# connection during a 15s AT+CMGS send would leave the caller hanging for up
# to 15s before finding out, instead of failing within one poll interval.
_DISCONNECT_POLL_INTERVAL: Final[float] = 0.25

# After a command times out, how long to keep `_command_active` set and keep
# draining `_command_queue` before handing routing back to the unsolicited
# queue. This absorbs a terminal response that the modem was in the middle of
# sending when our deadline expired, so it is discarded as a stale/late
# response to the timed-out command rather than being misrouted into
# `poll_events()` as if it were a fresh unsolicited event.
_STALE_RESPONSE_GRACE_SECONDS: Final[float] = 0.3

_SIMPLE_TERMINAL_TOKENS: Final[frozenset[str]] = frozenset(
    {"OK", "ERROR", "BUSY", "NO ANSWER", "NO CARRIER", "NO DIALTONE"}
)
_TERMINAL_ERROR_PREFIXES: Final[tuple[str, ...]] = ("+CME ERROR", "+CMS ERROR")

# Result codes that indicate a call attempt did not connect.
_CALL_MISSED_TOKENS: Final[frozenset[str]] = frozenset({"BUSY", "NO ANSWER", "NO DIALTONE"})
_CALL_FAILURE_TOKENS: Final[frozenset[str]] = _CALL_MISSED_TOKENS | {"NO CARRIER"}

# Modem-fatal unsolicited notifications: once one of these is observed, the
# modem is no longer safely commandable (it is powering off, or the SIM has
# been pulled) even though the serial port itself may still report as open.
# `domain.EventType` has no member for "modem lost power" or "SIM removed"
# (see module docstring / production_review.md), so these cannot be surfaced
# as a `TelephonyEvent`. Instead this is treated as equivalent to a transport
# disconnect: `_AtChannel.mark_fatal()` flips `disconnected`, so the next
# call into any public method drives the existing reconnect path, and any
# in-progress call is reported ended via the same synthetic-CALL_ENDED path
# used for a lost serial connection.
_FATAL_URC_PREFIXES: Final[tuple[str, ...]] = (
    "NORMAL POWER DOWN",
    "UNDER-VOLTAGE POWER DOWN",
    "UNDER-VOLTAGE WARNING",
    "OVER-VOLTAGE POWER DOWN",
    "OVER-VOLTAGE WARNING",
    "+CPIN: NOT READY",
    "+CPIN: NOT INSERTED",
)

# Unsolicited result codes that are real modem events but have no
# corresponding `domain.EventType` member and no safety-relevant side effect
# (unlike the fatal set above). Logged for diagnostics and otherwise
# intentionally dropped -- see production_review.md.
_UNMAPPED_URC_PREFIXES: Final[tuple[str, ...]] = (
    "+CDS:",   # SMS status report (delivery receipt)
    "+CUSD:",  # USSD response
    "+CREG:",  # network registration status change (post-init)
    "+CGREG:", # GPRS registration status change
    "+CGEV:",  # GPRS event
)


def _is_terminal_line(line: str) -> bool:
    """Return True if `line` is a final result code ending a command's response."""
    if line in _SIMPLE_TERMINAL_TOKENS:
        return True
    if line.startswith(_TERMINAL_ERROR_PREFIXES):
        return True
    if line.startswith("CONNECT"):
        return True
    return False


def _is_error_line(line: str) -> bool:
    """Return True if `line` indicates the preceding command failed."""
    if line == "ERROR":
        return True
    if line.startswith(_TERMINAL_ERROR_PREFIXES):
        return True
    if line in _CALL_FAILURE_TOKENS:
        return True
    return False


def _is_fatal_urc(line: str) -> bool:
    """Return True if `line` means the modem is no longer safely commandable."""
    return line.startswith(_FATAL_URC_PREFIXES)


def _is_unmapped_urc(line: str) -> bool:
    """Return True if `line` is a recognized-but-frozen-out-of-scope URC."""
    return line.startswith(_UNMAPPED_URC_PREFIXES)


class _ModemState(enum.Enum):
    """Coarse internal lifecycle state of the modem, tracked independently
    of any single AT response so that transient conditions (a call ringing,
    an SMS mid-send) are visible across the whole adapter, not just to
    whichever command happens to be in flight."""

    DISCONNECTED = "disconnected"
    INITIALIZING = "initializing"
    IDLE = "idle"
    DIALING = "dialing"
    RINGING = "ringing"
    CONNECTED = "connected"
    SMS_SENDING = "sms_sending"
    ERROR = "error"


class _SerialTransport:
    """Owns the raw pyserial connection. No AT-command knowledge lives here."""

    def __init__(self, port: str, baudrate: int, read_timeout: float) -> None:
        self._port = port
        self._baudrate = baudrate
        self._read_timeout = read_timeout
        self._serial: Optional[serial.Serial] = None
        self._write_lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def open(self) -> None:
        try:
            self._serial = serial.Serial(
                port=self._port,
                baudrate=self._baudrate,
                timeout=self._read_timeout,
            )
        except SerialException as exc:
            raise TelephonyUnavailableError(
                f"Could not open serial port {self._port!r} at {self._baudrate} baud: {exc}"
            ) from exc

    def close(self) -> None:
        if self._serial is not None:
            try:
                if self._serial.is_open:
                    self._serial.close()
            except SerialException as exc:
                logger.warning("Error closing serial port %s: %s", self._port, exc)
            finally:
                self._serial = None

    def read_chunk(self) -> bytes:
        """Blocking read of whatever is available, bounded by the serial timeout."""
        if self._serial is None:
            raise TelephonyUnavailableError(f"Serial port {self._port!r} is not open.")
        try:
            waiting = self._serial.in_waiting
            return self._serial.read(max(waiting, 1))
        except SerialException as exc:
            raise TelephonyUnavailableError(f"Serial read failure on {self._port!r}: {exc}") from exc

    def write(self, data: bytes) -> None:
        if self._serial is None:
            raise TelephonyUnavailableError(f"Serial port {self._port!r} is not open.")
        with self._write_lock:
            try:
                self._serial.write(data)
                self._serial.flush()
            except SerialException as exc:
                raise TelephonyUnavailableError(f"Serial write failure on {self._port!r}: {exc}") from exc


class _ReaderThread(threading.Thread):
    """Continuously tokenizes the serial stream into lines / the '>' prompt.

    Runs for the lifetime of one connection. On a serial I/O failure it
    reports the failure once (via `on_disconnect`) and exits; it never
    retries on its own -- reconnection is the adapter's responsibility.
    """

    def __init__(
        self,
        transport: _SerialTransport,
        on_line: Callable[[str], None],
        on_disconnect: Callable[[Exception], None],
    ) -> None:
        super().__init__(name="sim900a-reader", daemon=True)
        self._transport = transport
        self._on_line = on_line
        self._on_disconnect = on_disconnect
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        buffer = bytearray()
        while not self._stop_event.is_set():
            try:
                chunk = self._transport.read_chunk()
            except TelephonyUnavailableError as exc:
                self._on_disconnect(exc)
                return
            if not chunk:
                continue
            buffer.extend(chunk)
            self._drain_lines(buffer)

    def _drain_lines(self, buffer: bytearray) -> None:
        while True:
            newline_index = buffer.find(b"\n")
            if newline_index == -1:
                break
            raw_line = bytes(buffer[:newline_index])
            del buffer[: newline_index + 1]
            text = raw_line.decode(errors="ignore").strip("\r\n \t")
            if text:
                self._on_line(text)

        if bytes(buffer).strip() == _SMS_PROMPT.encode():
            self._on_line(_SMS_PROMPT)
            buffer.clear()
        elif len(buffer) > _MAX_LINE_BUFFER_BYTES:
            logger.warning(
                "Discarding %d bytes of unterminated serial data (buffer cap exceeded); "
                "treating as corrupted/noise.",
                len(buffer),
            )
            buffer.clear()


class _AtChannel:
    """Thread-safe AT-command request/response channel plus unsolicited feed.

    Exactly one command may be in flight at a time (`_command_lock`). While
    a command is in flight, every line the reader thread observes is routed
    to that command's response; once the command completes, subsequent
    lines are routed to the unsolicited queue until the next command starts.
    The flag flip and the routing decision share `_route_lock` so the two
    never interleave in a way that could misclassify a line.
    """

    def __init__(self, transport: _SerialTransport, default_timeout: float) -> None:
        self._transport = transport
        self._default_timeout = default_timeout
        self._command_lock = threading.Lock()
        self._route_lock = threading.Lock()
        self._command_active = False  # guarded by `_route_lock`
        self._command_queue: "queue.Queue[str]" = queue.Queue()
        self._unsolicited_queue: "queue.Queue[str]" = queue.Queue()
        self._reader: Optional[_ReaderThread] = None
        self.disconnected = threading.Event()

    def start(self) -> None:
        self.disconnected.clear()
        self._drain_queue(self._command_queue)
        with self._route_lock:
            self._command_active = False
        self._reader = _ReaderThread(self._transport, self._route_line, self._handle_disconnect)
        self._reader.start()

    def stop(self) -> None:
        if self._reader is not None:
            self._reader.stop()
            self._reader.join(timeout=2.0)
            self._reader = None

    @staticmethod
    def _drain_queue(target: "queue.Queue[str]") -> None:
        while True:
            try:
                target.get_nowait()
            except queue.Empty:
                return

    def _begin_command(self) -> None:
        with self._route_lock:
            self._command_active = True

    def _end_command(self) -> None:
        with self._route_lock:
            self._command_active = False

    def _route_line(self, line: str) -> None:
        with self._route_lock:
            if self._command_active:
                self._command_queue.put(line)
                return
            self._unsolicited_queue.put(line)
        size = self._unsolicited_queue.qsize()
        if size == _UNSOLICITED_QUEUE_WARN_THRESHOLD:
            logger.warning(
                "SIM900A unsolicited-event queue has grown to %d items; "
                "poll_events() may not be getting called frequently enough.",
                size,
            )

    def _handle_disconnect(self, exc: Exception) -> None:
        logger.error("SIM900A reader thread lost the serial connection: %s", exc)
        self.disconnected.set()

    def mark_fatal(self, reason: str) -> None:
        """Mark the channel unusable due to a fatal URC (power-down, SIM pulled).

        Reuses the same `disconnected` flag as a transport-level failure so
        every existing caller of `_ensure_connected` reconnects through the
        one path that already exists, instead of a second parallel one.
        """
        logger.error("SIM900A reported a fatal condition: %s", reason)
        self.disconnected.set()

    def _get_command_line_responsive(self, deadline: float, command_desc: str) -> str:
        """Block for the next command-queue line, re-checking `disconnected`
        every `_DISCONNECT_POLL_INTERVAL` instead of blocking for the whole
        remaining command timeout.

        Without this, a connection lost mid-command (e.g. USB unplug during
        a 15s AT+CMGS send) would leave the caller blocked for up to the
        full command timeout before finding out, instead of failing within
        one short poll interval.
        """
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._absorb_stale_response(command_desc)
                raise TelephonyUnavailableError(f"Timed out waiting for a response to {command_desc}.")
            if self.disconnected.is_set():
                raise TelephonyUnavailableError(
                    f"SIM900A connection lost while waiting for a response to {command_desc}."
                )
            try:
                return self._command_queue.get(timeout=min(remaining, _DISCONNECT_POLL_INTERVAL))
            except queue.Empty:
                continue

    def _absorb_stale_response(self, command_desc: str) -> None:
        """After a command times out, keep draining `_command_queue` for a
        short grace window before `_end_command()` hands routing back to the
        unsolicited queue.

        A modem that is merely slow (vs. genuinely unresponsive) may still be
        transmitting the terminal line for the command we just gave up on.
        Without this grace window, that line would land in the unsolicited
        queue moments later and could be misread by `poll_events()` as a
        fresh event (this is an inherent limitation of a half-duplex AT
        channel -- see production_review.md -- this grace window narrows the
        race but cannot close it completely).
        """
        grace_deadline = time.monotonic() + _STALE_RESPONSE_GRACE_SECONDS
        stale: list[str] = []
        while True:
            remaining = grace_deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                stale.append(self._command_queue.get(timeout=remaining))
            except queue.Empty:
                break
        if stale:
            logger.warning(
                "Discarding %d stale response line(s) that arrived after %s timed out: %r",
                len(stale),
                command_desc,
                stale,
            )

    def _write_and_collect_locked(self, command: str, deadline: float) -> list[str]:
        """Write `command` and collect its response lines until a terminal line.

        Caller must already hold `_command_lock` with `_command_active` set.
        """
        self._transport.write((command + "\r\n").encode())
        lines: list[str] = []
        stripped_command = command.strip()
        while True:
            line = self._get_command_line_responsive(deadline, repr(command))
            if line == stripped_command:
                continue  # command echo, in case ATE0 has not taken effect yet
            lines.append(line)
            if _is_terminal_line(line):
                return lines

    def send_command(self, command: str, *, timeout: Optional[float] = None) -> list[str]:
        """Send a single-line AT command and return its full response, in order."""
        if self.disconnected.is_set():
            raise TelephonyUnavailableError("SIM900A connection lost; reconnect required.")

        deadline = time.monotonic() + (timeout if timeout is not None else self._default_timeout)
        with self._command_lock:
            self._begin_command()
            try:
                return self._write_and_collect_locked(command, deadline)
            finally:
                self._end_command()

    def _set_character_set_locked(self, charset: str) -> None:
        """Switch the modem's TE character set. Caller must hold `_command_lock`."""
        deadline = time.monotonic() + self._default_timeout
        lines = self._write_and_collect_locked(f'AT+CSCS="{charset}"', deadline)
        if any(_is_error_line(line) for line in lines):
            raise SmsFailedError(f"SIM900A rejected character-set switch to {charset!r}: {lines}")

    @staticmethod
    def _encode_ucs2_hex(message: str) -> str:
        """Encode `message` as the hex-digit UCS2 (UTF-16BE) form SIM900A expects."""
        return message.encode("utf-16-be").hex().upper()

    def send_sms(self, number: str, message: str) -> str:
        """Run the full AT+CMGS prompt/body/Ctrl-Z exchange and return the message reference.

        Non-ASCII messages (e.g. Bengali text) are sent in UCS2 mode; the
        modem is switched back to the GSM character set afterward either way.
        """
        if self.disconnected.is_set():
            raise TelephonyUnavailableError("SIM900A connection lost; reconnect required.")

        use_ucs2 = not message.isascii()
        deadline = time.monotonic() + _SMS_SEND_TIMEOUT
        lines: list[str] = []

        with self._command_lock:
            self._begin_command()
            try:
                if use_ucs2:
                    self._set_character_set_locked("UCS2")
                try:
                    self._transport.write(f'AT+CMGS="{number}"\r\n'.encode())
                    if not self._wait_for_prompt(deadline):
                        raise SmsFailedError(
                            f"SIM900A did not present the '>' prompt for AT+CMGS to {number!r}."
                        )

                    body = self._encode_ucs2_hex(message) if use_ucs2 else message
                    self._transport.write(body.encode("ascii") + _CTRL_Z.encode())

                    while True:
                        line = self._get_command_line_responsive(
                            deadline, f"AT+CMGS confirmation for {number!r}"
                        )
                        lines.append(line)
                        if _is_terminal_line(line):
                            break
                finally:
                    if use_ucs2:
                        self._set_character_set_locked("GSM")
            finally:
                self._end_command()

        if any(_is_error_line(line) for line in lines):
            raise SmsFailedError(f"SIM900A rejected AT+CMGS to {number!r}: {lines}")

        for line in lines:
            match = re.match(r"\+CMGS:\s*(\d+)", line)
            if match:
                return match.group(1)

        raise SmsFailedError(
            f"SIM900A returned OK for AT+CMGS to {number!r} without a message reference: {lines}"
        )

    def _wait_for_prompt(self, deadline: float) -> bool:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            if self.disconnected.is_set():
                return False
            try:
                line = self._command_queue.get(timeout=min(remaining, _DISCONNECT_POLL_INTERVAL))
            except queue.Empty:
                continue
            if line == _SMS_PROMPT:
                return True
            logger.debug("Unexpected line while waiting for AT+CMGS prompt: %r", line)

    def drain_unsolicited(self) -> list[str]:
        """Return and clear all unsolicited lines accumulated since the last drain.

        The first line is waited for with a short bounded timeout (see
        `_UNSOLICITED_DRAIN_GRACE_SECONDS`) rather than a purely
        non-blocking check, so a line the reader thread is still in the
        process of routing is not missed. Everything after that first line
        is drained non-blocking, since by then the reader thread has
        already caught up.
        """
        lines: list[str] = []
        try:
            lines.append(self._unsolicited_queue.get(timeout=_UNSOLICITED_DRAIN_GRACE_SECONDS))
        except queue.Empty:
            return lines
        while True:
            try:
                lines.append(self._unsolicited_queue.get_nowait())
            except queue.Empty:
                return lines


class Sim900aAdapter(TelephonyInterface):
    """``TelephonyInterface`` implementation backed by a SIM900A modem.

    Args:
        port: Serial device path (e.g. ``/dev/ttyUSB0`` or ``COM3``).
        baudrate: Serial baud rate. SIM900A typically autobauds; 9600 and
            115200 are common fixed configurations.
        timeout: Default per-command response timeout, in seconds.

    The adapter owns a live serial connection and must be explicitly
    connected before use and disconnected when done::

        adapter = Sim900aAdapter(port="/dev/ttyUSB0", baudrate=9600)
        adapter.connect()
        try:
            ...
        finally:
            adapter.disconnect()

    or as an async context manager::

        async with Sim900aAdapter(port="/dev/ttyUSB0") as adapter:
            ...

    If the serial connection is lost, the next call into any
    ``TelephonyInterface`` method transparently attempts a bounded number of
    reconnect-and-reinitialize cycles before raising
    ``TelephonyUnavailableError``. Once ``disconnect()`` has been called
    explicitly, the adapter will not silently reconnect itself; ``connect()``
    must be called again first.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        timeout: float = _DEFAULT_COMMAND_TIMEOUT,
    ) -> None:
        self._transport = _SerialTransport(port=port, baudrate=baudrate, read_timeout=_SERIAL_READ_POLL_TIMEOUT)
        self._channel = _AtChannel(self._transport, default_timeout=timeout)

        self._lifecycle_lock = threading.Lock()
        self._ready_event = threading.Event()
        self._intentionally_disconnected = threading.Event()

        # Serializes the multi-step place_call() and hangup() sequences
        # against each other (SIM900A has a single voice channel).
        self._call_operation_lock = threading.Lock()
        # Serializes send_sms() state bookkeeping against itself; the wire
        # exchange is already serialized by `_AtChannel._command_lock`, but
        # the SMS_SENDING/previous-state transition here needs its own
        # matching serialization or two overlapping sends can restore each
        # other's state incorrectly.
        self._sms_lock = threading.Lock()
        # Serializes poll_events() so a caller always drains a consistent,
        # non-interleaved batch of synthetic + unsolicited events.
        self._poll_lock = threading.Lock()

        self._state_lock = threading.Lock()
        self._state = _ModemState.DISCONNECTED

        self._call_lock = threading.Lock()
        self._active_call: Optional[CallHandle] = None
        self._last_caller_number: Optional[str] = None
        self._synthetic_events: list[TelephonyEvent] = []

    # -- connection lifecycle ---------------------------------------------

    @property
    def state(self) -> str:
        """Current coarse modem state, for diagnostics/monitoring only.

        Not part of ``TelephonyInterface``; the Queue Engine must not read
        this, since it may only depend on the interface contract.
        """
        return self._get_state().value

    def _get_state(self) -> _ModemState:
        with self._state_lock:
            return self._state

    def _set_state(self, state: _ModemState) -> None:
        with self._state_lock:
            if self._state is not state:
                logger.debug("SIM900A modem state transition: %s -> %s", self._state.value, state.value)
            self._state = state

    def connect(self) -> None:
        """Open the serial port, start the reader thread, and initialize the modem.

        Raises:
            TelephonyUnavailableError: the port cannot be opened, the SIM is
                not ready, the modem is not registered, or initialization
                otherwise fails.
        """
        with self._lifecycle_lock:
            self._intentionally_disconnected.clear()
            if self._ready_event.is_set() or self._transport.is_open:
                # connect() called while already connected: tear down the
                # existing reader thread and serial handle first, the same
                # way the reconnect path in `_ensure_connected` already does,
                # so we never end up with two live `_ReaderThread`s racing
                # on the same serial connection or an orphaned thread that
                # `disconnect()` can no longer reach.
                logger.warning(
                    "SIM900A connect() called while already connected; "
                    "tearing down the previous connection first."
                )
                self._teardown_locked()
            self._transport.open()
            try:
                self._channel.start()
                self._initialize_modem()
            except Exception:
                self._teardown_locked()
                raise
            self._set_state(_ModemState.IDLE)
            self._ready_event.set()

    def disconnect(self) -> None:
        """Stop the reader thread and close the serial port. Safe to call repeatedly.

        After this, the adapter will not reconnect on its own; call
        ``connect()`` again to resume use.
        """
        with self._lifecycle_lock:
            self._intentionally_disconnected.set()
            self._teardown_locked()

    def _teardown_locked(self) -> None:
        """Tear down reader thread + serial port. Caller must hold `_lifecycle_lock`."""
        self._ready_event.clear()
        self._channel.stop()
        self._transport.close()
        self._set_state(_ModemState.DISCONNECTED)
        with self._call_lock:
            lost_call = self._active_call
            self._active_call = None
            if lost_call is not None:
                self._synthetic_events.append(
                    TelephonyEvent(
                        event_type=EventType.CALL_ENDED,
                        phone_number=lost_call.phone_number,
                        call_id=lost_call.call_id,
                    )
                )

    async def __aenter__(self) -> "Sim900aAdapter":
        await asyncio.to_thread(self.connect)
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await asyncio.to_thread(self.disconnect)

    def _ensure_connected(self) -> None:
        """Verify the connection is live and initialized, reconnecting if not.

        `_ready_event` is only ever set once a full connect/reconnect cycle
        has completed successfully, so a thread observing it set can safely
        issue commands immediately -- there is no window in which one thread
        has started reinitializing while another believes the modem is idle.
        """
        if self._ready_event.is_set() and not self._channel.disconnected.is_set():
            return

        with self._lifecycle_lock:
            if self._ready_event.is_set() and not self._channel.disconnected.is_set():
                return

            if self._intentionally_disconnected.is_set():
                raise TelephonyUnavailableError(
                    "SIM900A adapter has been explicitly disconnected; call connect() to resume."
                )

            logger.warning("SIM900A connection unavailable; attempting reconnect.")
            self._teardown_locked()

            last_exc: Optional[BaseException] = None
            for attempt in range(1, _RECONNECT_ATTEMPTS + 1):
                try:
                    self._transport.open()
                    self._channel.start()
                    self._initialize_modem()
                    self._set_state(_ModemState.IDLE)
                    self._ready_event.set()
                    logger.info("SIM900A reconnected successfully on attempt %d.", attempt)
                    return
                except TelephonyError as exc:
                    last_exc = exc
                    self._teardown_locked()
                    time.sleep(_RECONNECT_BACKOFF_SECONDS * attempt)
                except Exception as exc:  # unexpected failure, e.g. OS-level thread-start error
                    last_exc = exc
                    logger.exception("Unexpected error during SIM900A reconnect attempt %d.", attempt)
                    self._teardown_locked()
                    time.sleep(_RECONNECT_BACKOFF_SECONDS * attempt)

            raise TelephonyUnavailableError(
                f"SIM900A reconnect failed after {_RECONNECT_ATTEMPTS} attempts: {last_exc}"
            )

    def _initialize_modem(self) -> None:
        """Bring the modem to a known-good state for calls and SMS."""
        self._set_state(_ModemState.INITIALIZING)

        self._channel.send_command("AT")
        self._channel.send_command("ATE0")  # disable command echo

        pin_status = self._channel.send_command("AT+CPIN?")
        if not any("READY" in line for line in pin_status):
            raise TelephonyUnavailableError(
                f"SIM900A SIM is not ready (AT+CPIN? returned {pin_status!r})."
            )

        registration = self._channel.send_command("AT+CREG?")
        if not any(re.search(r"\+CREG:\s*\d,\s*[15]", line) for line in registration):
            raise TelephonyUnavailableError(
                f"SIM900A is not registered on the network (AT+CREG? returned {registration!r})."
            )

        try:
            self._channel.send_command("AT+CSQ")
        except TelephonyUnavailableError:
            raise
        except TelephonyError as exc:
            logger.warning("AT+CSQ signal-quality check failed (non-fatal): %s", exc)

        self._channel.send_command("AT+CMGF=1")  # text-mode SMS

        try:
            self._channel.send_command('AT+CSCS="GSM"')  # default character set for ASCII SMS
        except TelephonyError as exc:
            logger.warning("AT+CSCS=\"GSM\" failed (default character set may differ): %s", exc)

        try:
            self._channel.send_command("AT+CNMI=2,2,0,0,0")  # push full SMS text via +CMT
        except TelephonyError as exc:
            logger.warning("AT+CNMI configuration failed (SMS events may be delayed): %s", exc)

        try:
            self._channel.send_command("AT+CLIP=1")  # enable caller-ID for incoming calls
        except TelephonyError as exc:
            logger.warning("AT+CLIP=1 failed; incoming caller numbers may be unavailable: %s", exc)

    # -- TelephonyInterface --------------------------------------------------

    async def place_call(self, request: CallRequest) -> CallHandle:
        number = self._validate_number(request.phone_number)
        return await asyncio.to_thread(self._place_call_sync, number)

    def _place_call_sync(self, number: str) -> CallHandle:
        self._ensure_connected()
        with self._call_operation_lock:
            with self._call_lock:
                if self._active_call is not None:
                    raise CallFailedError(
                        f"Cannot place call to {number!r}: a call to "
                        f"{self._active_call.phone_number!r} is already active."
                    )

            self._set_state(_ModemState.DIALING)
            try:
                lines = self._channel.send_command(f"ATD{number};", timeout=_CALL_SETUP_TIMEOUT)
            except TelephonyUnavailableError:
                self._set_state(_ModemState.ERROR)
                raise
            except TelephonyError as exc:
                self._set_state(_ModemState.IDLE)
                raise CallFailedError(f"SIM900A failed to place call to {number!r}: {exc}") from exc

            if any(_is_error_line(line) for line in lines):
                self._set_state(_ModemState.IDLE)
                raise CallFailedError(f"SIM900A failed to connect call to {number!r}: {lines}")

            handle = CallHandle(call_id=f"sim900a-{uuid.uuid4().hex}", phone_number=number)
            with self._call_lock:
                self._active_call = handle
            # Do NOT transition to CONNECTED here: `ATD<number>;` returning OK
            # only means dialing has started. The modem reports the actual
            # outcome (CONNECT/BUSY/NO ANSWER/NO CARRIER) asynchronously as a
            # URC, handled by `_parse_unsolicited_line`, which is the sole
            # place that should transition the state to CONNECTED.
            return handle

    async def send_sms(self, request: SmsRequest) -> SmsHandle:
        number = self._validate_number(request.phone_number)
        return await asyncio.to_thread(self._send_sms_sync, number, request.message)

    def _send_sms_sync(self, number: str, message: str) -> SmsHandle:
        self._ensure_connected()
        with self._sms_lock:
            previous_state = self._get_state()
            self._set_state(_ModemState.SMS_SENDING)
            try:
                message_id = self._channel.send_sms(number, message)
            except TelephonyUnavailableError:
                self._set_state(_ModemState.ERROR)
                raise
            except TelephonyError as exc:
                self._set_state(previous_state)
                raise SmsFailedError(f"SIM900A failed to send SMS to {number!r}: {exc}") from exc
            self._set_state(previous_state)
        return SmsHandle(message_id=message_id, phone_number=number)

    async def hangup(self, call_id: str) -> None:
        await asyncio.to_thread(self._hangup_sync, call_id)

    def _hangup_sync(self, call_id: str) -> None:
        self._ensure_connected()
        with self._call_operation_lock:
            with self._call_lock:
                active = self._active_call

            if active is None:
                logger.debug(
                    "Hangup requested for call %r but no call is currently active; "
                    "treating it as already ended.",
                    call_id,
                )
                return

            if active.call_id != call_id:
                raise CallFailedError(
                    f"Cannot hang up call {call_id!r}: a different call "
                    f"({active.call_id!r}) is currently active."
                )

            try:
                self._channel.send_command("ATH")
            except TelephonyUnavailableError:
                self._set_state(_ModemState.ERROR)
                raise
            except TelephonyError as exc:
                with self._call_lock:
                    self._active_call = None
                self._set_state(_ModemState.IDLE)
                raise CallFailedError(f"SIM900A failed to hang up call {call_id!r}: {exc}") from exc

            with self._call_lock:
                self._active_call = None
            self._set_state(_ModemState.IDLE)

    async def poll_events(self) -> list[TelephonyEvent]:
        return await asyncio.to_thread(self._poll_events_sync)

    def _poll_events_sync(self) -> list[TelephonyEvent]:
        try:
            self._ensure_connected()
        except TelephonyUnavailableError:
            # Command methods (place_call/send_sms/hangup) must keep
            # rejecting after an explicit disconnect() -- that behavior is
            # untouched. poll_events() is different: its job includes
            # draining `_synthetic_events` (e.g. the CALL_ENDED synthesized
            # by `_teardown_locked` for a call lost to that same
            # disconnect), and the caller must still learn that even though
            # the adapter is not currently connected. Only bypass the raise
            # for that specific "intentionally disconnected" case; any other
            # connectivity failure (e.g. reconnect exhausted) still raises.
            if not self._intentionally_disconnected.is_set():
                raise
            with self._poll_lock:
                with self._call_lock:
                    synthetic_events = self._synthetic_events
                    self._synthetic_events = []
                return list(synthetic_events)
        with self._poll_lock:
            with self._call_lock:
                synthetic_events = self._synthetic_events
                self._synthetic_events = []

            lines = self._channel.drain_unsolicited()
            events: list[TelephonyEvent] = list(synthetic_events)
            index = 0
            while index < len(lines):
                consumed, event = self._parse_unsolicited_line(lines, index)
                if event is not None:
                    events.append(event)
                index += consumed
            return events

    def _parse_unsolicited_line(
        self,
        lines: list[str],
        index: int,
    ) -> tuple[int, Optional[TelephonyEvent]]:
        """Parse one unsolicited line, returning (lines_consumed, event_or_None)."""
        line = lines[index]

        if _is_fatal_urc(line):
            # Modem is powering off or the SIM was pulled. No `EventType`
            # member exists for this (see module docstring and
            # production_review.md); the best we can do without modifying
            # the frozen domain model is (a) stop pretending the modem is
            # usable, so the next call reconnects instead of timing out
            # against a dead modem, and (b) tell the Queue Engine the active
            # call, if any, is over -- via the one event type that already
            # exists for "this call is no longer live".
            self._channel.mark_fatal(line)
            self._set_state(_ModemState.ERROR)
            number, call_id = self._consume_active_call()
            if call_id is not None:
                return 1, TelephonyEvent(
                    event_type=EventType.CALL_ENDED,
                    phone_number=number,
                    call_id=call_id,
                )
            return 1, None

        if _is_unmapped_urc(line):
            # Real modem notification (delivery report, USSD, registration/
            # GPRS status change) with no corresponding EventType member and
            # no safety-relevant side effect. Logged for diagnostics and
            # intentionally not surfaced -- see production_review.md.
            logger.info("SIM900A unmapped URC (no EventType to carry it): %r", line)
            return 1, None

        if line.startswith("+CLIP:"):
            with self._call_lock:
                self._last_caller_number = self._extract_quoted_number(line)
            return 1, None

        if line == "RING":
            self._set_state(_ModemState.RINGING)
            with self._call_lock:
                number = self._last_caller_number or "unknown"
            return 1, TelephonyEvent(
                event_type=EventType.INCOMING_CALL,
                phone_number=number,
                direction=CallDirection.INBOUND,
            )

        if line.startswith("CONNECT"):
            self._set_state(_ModemState.CONNECTED)
            with self._call_lock:
                active = self._active_call
                number = active.phone_number if active else (self._last_caller_number or "unknown")
                call_id = active.call_id if active else None
            return 1, TelephonyEvent(
                event_type=EventType.CALL_ANSWERED,
                phone_number=number,
                call_id=call_id,
                direction=CallDirection.OUTBOUND if active else CallDirection.INBOUND,
            )

        if line == "NO CARRIER":
            number, call_id = self._consume_active_call()
            self._set_state(_ModemState.IDLE)
            return 1, TelephonyEvent(
                event_type=EventType.CALL_ENDED,
                phone_number=number,
                call_id=call_id,
            )

        if line in _CALL_MISSED_TOKENS:
            number, call_id = self._consume_active_call()
            self._set_state(_ModemState.IDLE)
            return 1, TelephonyEvent(
                event_type=EventType.CALL_MISSED,
                phone_number=number,
                call_id=call_id,
            )

        if line.startswith("+CMT:"):
            number = self._extract_quoted_number(line)
            body = lines[index + 1] if index + 1 < len(lines) else None
            return 2, TelephonyEvent(
                event_type=EventType.SMS_RECEIVED,
                phone_number=number or "unknown",
                message=body,
            )

        if line.startswith("+CMTI:"):
            # SMS stored to memory only (index notification, no header/body
            # inline). AT+CNMI is configured for mode 2 (direct +CMT push)
            # during init, so this path is a fallback -- e.g. the modem's
            # internal buffer overflowed and it fell back to storage mode.
            # Fetch the real content with AT+CMGR so a fallback SMS is not
            # silently reduced to an empty placeholder, then free the slot
            # with AT+CMGD so storage does not fill up over a long-running
            # deployment.
            return 1, self._fetch_stored_sms(line)

        return 1, None

    def _fetch_stored_sms(self, cmti_line: str) -> TelephonyEvent:
        """Read and delete the message `cmti_line` announced, via AT+CMGR/AT+CMGD.

        Falls back to an empty placeholder (never raises) if the index can't
        be parsed or the modem rejects the follow-up read, since a poll_events()
        caller should still learn *that* a message arrived even if its content
        couldn't be recovered.
        """
        match = re.search(r",\s*(\d+)\s*$", cmti_line)
        if not match:
            logger.warning(
                "Could not parse a storage index out of %r; surfacing an empty placeholder.",
                cmti_line,
            )
            return TelephonyEvent(event_type=EventType.SMS_RECEIVED, phone_number="unknown", message=None)

        index = match.group(1)
        try:
            lines = self._channel.send_command(f"AT+CMGR={index}")
        except TelephonyError as exc:
            logger.warning(
                "AT+CMGR=%s failed (%s); surfacing an empty placeholder for %r.", index, exc, cmti_line
            )
            return TelephonyEvent(event_type=EventType.SMS_RECEIVED, phone_number="unknown", message=None)

        number: Optional[str] = None
        body_parts: list[str] = []
        for line in lines:
            if line.startswith("+CMGR:"):
                number = self._extract_quoted_number(line)
            elif line == "OK" or _is_error_line(line):
                continue
            else:
                body_parts.append(line)
        message = "\n".join(body_parts) if body_parts else None

        try:
            self._channel.send_command(f"AT+CMGD={index}")
        except TelephonyError as exc:
            logger.warning("AT+CMGD=%s failed (%s); stored message slot was not freed.", index, exc)

        return TelephonyEvent(
            event_type=EventType.SMS_RECEIVED,
            phone_number=number or "unknown",
            message=message,
        )

    def _consume_active_call(self) -> tuple[str, Optional[str]]:
        with self._call_lock:
            active = self._active_call
            self._active_call = None
        if active is not None:
            return active.phone_number, active.call_id
        return "unknown", None

    @staticmethod
    def _extract_quoted_number(line: str) -> Optional[str]:
        match = re.search(r'"(\+?[0-9]+)"', line)
        return match.group(1) if match else None

    @staticmethod
    def _validate_number(phone_number: str) -> str:
        if not _PHONE_NUMBER_PATTERN.match(phone_number):
            raise InvalidPhoneNumberError(f"Invalid phone number: {phone_number!r}")
        return phone_number
