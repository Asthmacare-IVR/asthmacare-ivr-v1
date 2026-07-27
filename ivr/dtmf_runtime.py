"""
DTMF runtime collection and validation utilities for IVR.
"""

import logging
from typing import Optional
from ivr.dtmf import normalize_digits, validate_patient_id, classify_patient_id_input
from ivr.models import DTMFResult

logger = logging.getLogger(__name__)


class DTMFRuntime:
    """Handles runtime collection and validation of DTMF inputs from callers using existing PR-1 dtmf functions."""

    def __init__(self, telephony_interface, default_timeout_sec: float = 5.0):
        """
        Initialize the DTMF runtime collector.

        Args:
            telephony_interface: The telephony interface used to receive digits.
            default_timeout_sec: Default timeout waiting for digit input.
        """
        self.telephony = telephony_interface
        self.default_timeout_sec = default_timeout_sec

    def collect_digit(self, timeout_sec: Optional[float] = None) -> Optional[str]:
        """
        Collect a single DTMF digit from the caller.

        Args:
            timeout_sec: Timeout override in seconds.

        Returns:
            String containing the collected digit, or None if timed out.
        """
        timeout = timeout_sec if timeout_sec is not None else self.default_timeout_sec
        logger.info("Collecting single DTMF digit with timeout %.1fs", timeout)

        try:
            if hasattr(self.telephony, "read_dtmf"):
                digit = self.telephony.read_dtmf(max_digits=1, timeout=timeout)
                return digit if digit else None
            elif hasattr(self.telephony, "collect"):
                raw = self.telephony.collect(timeout_seconds=timeout)
                return raw if raw else None
            else:
                logger.warning("Telephony interface lacks collection method.")
                return None
        except Exception as e:
            logger.error("Error collecting DTMF digit: %s", e)
            return None

    def collect_multi_digits(self, max_digits: int = 12, terminator: str = "#", timeout_sec: Optional[float] = None) -> Optional[str]:
        """
        Collect multiple DTMF digits until terminator or max length is reached.

        Args:
            max_digits: Maximum number of digits to collect.
            terminator: Character that ends collection prematurely.
            timeout_sec: Timeout override in seconds.

        Returns:
            Raw collected string or None.
        """
        timeout = timeout_sec if timeout_sec is not None else self.default_timeout_sec
        logger.info("Collecting up to %s DTMF digits (terminator: %s)", max_digits, terminator)

        try:
            if hasattr(self.telephony, "read_dtmf"):
                return self.telephony.read_dtmf(max_digits=max_digits, timeout=timeout)
            elif hasattr(self.telephony, "collect"):
                return self.telephony.collect(timeout_seconds=timeout)
            else:
                return None
        except Exception as e:
            logger.error("Error collecting multi-digits: %s", e)
            return None

    def classify_and_normalize(self, raw_input: Optional[str]) -> DTMFResult:
        """
        Classify raw input using existing classify_patient_id_input.

        Args:
            raw_input: Raw input string from telephony collector.

        Returns:
            DTMFResult enum value.
        """
        return classify_patient_id_input(raw_input)