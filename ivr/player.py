"""Prompt playback abstraction — ISSUE #5 PR-2A.

`PromptPlayer` is `ivr.runtime.IVRRuntime`'s dependency-injected
playback boundary. No audio, TTS, or telephony playback command is
implemented here, or anywhere in this PR — see `ivr/prompts.py` for the
prompt text this plays, and docs/IVR_STATE_MACHINE.md "Future
Integration Points" #1 for where a real TTS/audio-file player is
expected to plug in later.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class PromptPlayer(ABC):
    """Something capable of speaking a prompt to an active call.

    Async to match the rest of the runtime's telephony-facing surface
    (`telephony.interface.TelephonyInterface` is entirely async); a real
    implementation backed by TTS or a pre-recorded audio file is
    naturally I/O-bound.
    """

    @abstractmethod
    async def play(self, prompt: str) -> None:
        """Play `prompt` to completion (or raise on failure).

        The runtime awaits this before continuing the workflow, so a
        real implementation should not return until the prompt has
        actually finished (or been definitively abandoned) — the
        runtime uses the return of this call as its synchronization
        point for "the caller has now heard this prompt".
        """

    @abstractmethod
    async def stop(self) -> None:
        """Stop whatever is currently playing, if anything.

        Must be safe to call when nothing is playing. The runtime calls
        this when a call ends before a prompt finishes speaking.
        """
