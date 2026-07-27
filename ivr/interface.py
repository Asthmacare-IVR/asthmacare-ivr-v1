"""IVR Workflow Interface — abstract contract for ivr/.

Anything driving a call (a future telephony adapter, a future backend
endpoint) depends only on this abstraction, never on `DefaultIVRWorkflow`
directly — the same dependency-inversion shape as
`database/interfaces.py` uses for repositories. This PR defines the
contract and its pure in-memory implementation only; no telephony, DTMF
collection, queue engine, or persistence code is wired to it yet (see
docs/IVR_STATE_MACHINE.md, "Future integration points").
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ivr.models import IVRState


class IVRWorkflow(ABC):
    """A single call's progression through the IVR state machine."""

    @abstractmethod
    def start(self) -> IVRState:
        """Begin the workflow: START → WELCOME.

        Raises WorkflowFinishedError if the workflow is already
        terminal, or InvalidTransitionError if it has already been
        started (call reset() first).
        """

    @abstractmethod
    def next(self) -> IVRState:
        """Advance to the next state along the current path (the happy
        path, or from FAILED to END).

        Raises WorkflowFinishedError if the workflow is already
        terminal, or InvalidTransitionError if start() has not been
        called yet.
        """

    @abstractmethod
    def reset(self) -> None:
        """Return the workflow to its initial START state."""

    @abstractmethod
    def current_state(self) -> IVRState:
        """Return the workflow's current state."""

    @abstractmethod
    def is_finished(self) -> bool:
        """Whether the workflow has reached its terminal state."""
