"""IVR prompt text — constants only.

These are the strings a future telephony-playback layer will speak (via
TTS or pre-recorded audio) at each step of the call flow. No audio
playback, no TTS integration, no file paths — that belongs to a later
PR (telephony adapter work).
"""

from __future__ import annotations

WELCOME_PROMPT = "Welcome to AsthmaCare. Please stay on the line."
PATIENT_ID_PROMPT = "Please enter your patient ID followed by the pound key."
CONFIRMATION_PROMPT = "You have been added to the queue. Press 1 to confirm."
GOODBYE_PROMPT = "Thank you for calling AsthmaCare. Goodbye."
