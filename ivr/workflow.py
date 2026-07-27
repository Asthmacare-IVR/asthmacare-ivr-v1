"""Default IVR Workflow implementation — pure state transitions only.

No telephony, no backend API, no database. `DefaultIVRWorkflow` holds an
`IVRContext` in memory and delegates every transition decision to
`IVRStateMachine`; it never decides on its own whether a transition is
legal.
"""

from __future__ import annotations

from ivr.exceptions import InvalidTransitionError, WorkflowFinishedError
from ivr.interface import IVRWorkflow
from ivr.models import IVRContext, IVRState
from ivr.state_machine import IVRStateMachine


class DefaultIVRWorkflow(IVRWorkflow):
    """Pure, dependency-free implementation of `IVRWorkflow`.

    Usage::

        workflow = DefaultIVRWorkflow(IVRContext(call_id="c1", phone_number="+1..."))
        workflow.start()          # START -> WELCOME
        workflow.next()           # WELCOME -> PATIENT_IDENTIFICATION
        ...
    """

    def __init__(self, context: IVRContext | None = None) -> None:
        self._context = context if context is not None else IVRContext(call_id="", phone_number="")
        self._state_machine = IVRStateMachine()

    def start(self) -> IVRState:
        if self.is_finished():
            raise WorkflowFinishedError("Cannot start a finished workflow; call reset() first")
        if self._context.current_state != IVRState.START:
            raise InvalidTransitionError("start() may only be called from the START state")
        return self._advance_to(IVRState.WELCOME)

    def next(self) -> IVRState:
        if self.is_finished():
            raise WorkflowFinishedError("Workflow has already finished")
        if self._context.current_state == IVRState.START:
            raise InvalidTransitionError("start() must be called before next()")
        target = self._state_machine.get_next(self._context.current_state)
        if target is None:
            raise InvalidTransitionError(
                f"No successor state from {self._context.current_state.value}"
            )
        return self._advance_to(target)

    def fail(self, reason: str = "") -> IVRState:
        """Explicitly branch to FAILED (e.g. max invalid-input attempts
        exceeded, caller hung up).

        This is intentionally not part of `IVRWorkflow`'s abstract
        contract — failure is an exceptional branch triggered by an
        external signal (DTMF timeout, invalid input), not a step in the
        start()/next() happy path. It is exposed here, on the concrete
        implementation, as the extension point later PRs (DTMF
        collection, queue engine integration) are expected to call.
        """
        if self.is_finished():
            raise WorkflowFinishedError("Workflow has already finished")
        if not self._state_machine.can_fail(self._context.current_state):
            raise InvalidTransitionError(f"Cannot fail from {self._context.current_state.value}")
        if reason:
            self._context.metadata["failure_reason"] = reason
        return self._advance_to(IVRState.FAILED)

    def reset(self) -> None:
        """Return to START and clear the retry counter. Call identity
        (`call_id`, `phone_number`, `patient_id`) and `metadata` are left
        untouched — a reset restarts the flow for the same call, it does
        not forget the call."""
        self._context.current_state = IVRState.START
        self._context.attempts = 0

    def current_state(self) -> IVRState:
        return self._context.current_state

    def is_finished(self) -> bool:
        return self._state_machine.is_terminal(self._context.current_state)

    def _advance_to(self, target: IVRState) -> IVRState:
        self._state_machine.assert_valid(self._context.current_state, target)
        self._context.current_state = target
        return target
