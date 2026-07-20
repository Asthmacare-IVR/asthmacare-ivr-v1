class TelephonyError(Exception):
    """Base exception for all telephony-related failures."""


class CallFailedError(TelephonyError):
    """Raised when a call cannot be initiated."""


class SmsFailedError(TelephonyError):
    """Raised when an SMS cannot be sent."""


class InvalidPhoneNumberError(TelephonyError):
    """Raised when a phone number is invalid."""


class TelephonyUnavailableError(TelephonyError):
    """Raised when the telephony backend is unavailable."""