"""Simulated SIM900A serial backend for unit tests."""

from __future__ import annotations

import re
import threading
import time
from typing import Callable, Optional


class FakeSerialPort:
    """Thread-safe fake serial port that simulates a SIM900A modem."""

    def __init__(
        self,
        *,
        registered: bool = True,
        sim_ready: bool = True,
        on_command: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.is_open = False
        self.timeout = 0.2
        self.in_waiting = 0
        self._registered = registered
        self._sim_ready = sim_ready
        self._on_command = on_command
        self._rx = bytearray()
        self._tx = bytearray()
        self._lock = threading.RLock()
        self._pending_sms_number: Optional[str] = None

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    def write(self, data: bytes) -> int:
        with self._lock:
            self._tx.extend(data)
            text = data.decode("ascii", errors="ignore")
            for line in text.split("\r\n"):
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped == _CTRL_Z:
                    self._handle_sms_body()
                    continue
                if self._pending_sms_number is not None and stripped != _CTRL_Z:
                    self._handle_sms_body(stripped)
                    continue
                self._handle_command(stripped)
        return len(data)

    def flush(self) -> None:
        return None

    def read(self, size: int) -> bytes:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            with self._lock:
                if self._rx:
                    chunk = bytes(self._rx[:size])
                    del self._rx[: len(chunk)]
                    self.in_waiting = len(self._rx)
                    return chunk
            time.sleep(0.01)
        return b""

    def inject(self, *lines: str) -> None:
        """Inject unsolicited modem output (e.g. RING, +CMT)."""
        payload = "".join(f"{line}\r\n" for line in lines)
        with self._lock:
            self._rx.extend(payload.encode("ascii"))
            self.in_waiting = len(self._rx)

    def written(self) -> str:
        with self._lock:
            return self._tx.decode("ascii", errors="ignore")

    def clear_written(self) -> None:
        with self._lock:
            self._tx.clear()

    def _enqueue(self, *lines: str) -> None:
        payload = "".join(f"{line}\r\n" for line in lines)
        with self._lock:
            self._rx.extend(payload.encode("ascii"))
            self.in_waiting = len(self._rx)

    def _handle_command(self, command: str) -> None:
        if self._on_command:
            self._on_command(command)

        if command == "AT":
            self._enqueue("OK")
        elif command == "ATE0":
            self._enqueue("OK")
        elif command == "AT+CPIN?":
            if self._sim_ready:
                self._enqueue("+CPIN: READY", "OK")
            else:
                self._enqueue("+CME ERROR: 10", "ERROR")
        elif command == "AT+CREG?":
            if self._registered:
                self._enqueue("+CREG: 0,1", "OK")
            else:
                self._enqueue("+CREG: 0,0", "OK")
        elif command == "AT+CSQ":
            self._enqueue("+CSQ: 20,0", "OK")
        elif command == "AT+CMGF=1":
            self._enqueue("OK")
        elif command.startswith('AT+CSCS="'):
            self._enqueue("OK")
        elif command == "AT+CNMI=2,2,0,0,0":
            self._enqueue("OK")
        elif command == "AT+CLIP=1":
            self._enqueue("OK")
        elif command.startswith("ATD") and command.endswith(";"):
            self._enqueue("OK")
        elif command == "ATH":
            self._enqueue("OK")
        elif command.startswith('AT+CMGS="'):
            match = re.match(r'AT\+CMGS="(\+?[0-9]+)"', command)
            self._pending_sms_number = match.group(1) if match else "unknown"
            self._enqueue(">")
        else:
            self._enqueue("ERROR")

    def _handle_sms_body(self, body: str = "") -> None:
        self._pending_sms_number = None
        self._enqueue("+CMGS: 42", "OK")


_CTRL_Z = "\x1a"
