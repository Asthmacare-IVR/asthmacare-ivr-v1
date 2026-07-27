"""
Prompt player abstraction for IVR runtime audio playback.
"""

from abc import ABC, abstractmethod
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class PromptPlayerInterface(ABC):
    """Abstract base interface for playing audio prompts over a telephony channel."""

    @abstractmethod
    def play_prompt(self, prompt_name: str, allow_interruption: bool = True) -> Optional[str]:
        """
        Play a named prompt to the active call session.
        
        Args:
            prompt_name: Identifier or key of the prompt to play.
            allow_interruption: Whether user DTMF input can interrupt playback.
            
        Returns:
            Optional string containing the interrupting DTMF digit if any, otherwise None.
        """
        pass

    @abstractmethod
    def play_sequence(self, prompt_sequence: List[str], allow_interruption: bool = True) -> Optional[str]:
        """
        Play a sequence of prompts back-to-back.
        
        Args:
            prompt_sequence: Ordered list of prompt identifiers.
            allow_interruption: Whether user DTMF input can interrupt playback.
            
        Returns:
            Optional string containing the interrupting DTMF digit if any, otherwise None.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop any active prompt playback immediately."""
        pass


class SIM900APromptPlayer(PromptPlayerInterface):
    """Prompt player implementation utilizing the SIM900A telephony interface."""

    def __init__(self, telephony_interface, prompts_dict: Optional[dict] = None):
        """
        Initialize the prompt player.

        Args:
            telephony_interface: The underlying telephony driver/interface.
            prompts_dict: Optional mapping of prompt names to audio file paths or codes.
        """
        self.telephony = telephony_interface
        self.prompts_dict = prompts_dict or {}

    def play_prompt(self, prompt_name: str, allow_interruption: bool = True) -> Optional[str]:
        logger.info("Playing prompt '%s' (interruption allowed: %s)", prompt_name, allow_interruption)
        prompt_ref = self.prompts_dict.get(prompt_name, prompt_name)
        
        try:
            if hasattr(self.telephony, "play_audio"):
                result = self.telephony.play_audio(prompt_ref, interruptible=allow_interruption)
                return result
            else:
                logger.warning("Telephony interface does not support play_audio. Simulating playback.")
                return None
        except Exception as e:
            logger.error("Error playing prompt '%s': %s", prompt_name, e)
            raise

    def play_sequence(self, prompt_sequence: List[str], allow_interruption: bool = True) -> Optional[str]:
        logger.info("Playing prompt sequence: %s", prompt_sequence)
        for prompt_name in prompt_sequence:
            digit = self.play_prompt(prompt_name, allow_interruption=allow_interruption)
            if digit is not None:
                return digit
        return None

    def stop(self) -> None:
        logger.info("Stopping prompt playback")
        if hasattr(self.telephony, "stop_audio"):
            self.telephony.stop_audio()