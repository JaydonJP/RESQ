"""Deterministic intersection controller; ML never owns a signal transition."""

from dataclasses import dataclass
from datetime import UTC, datetime

from schema import PriorityRequest, SignalPhase, SignalState


@dataclass(frozen=True, slots=True)
class CorridorTimings:
    minimum_green_s: float = 5.0
    amber_s: float = 3.0
    all_red_s: float = 2.0
    maximum_preemption_s: float = 60.0
    recovery_s: float = 8.0


class IntersectionController:
    def __init__(self, intersection_id: str, timings: CorridorTimings | None = None) -> None:
        self.intersection_id = intersection_id
        self.timings = timings or CorridorTimings()
        self.phase = SignalPhase.NORMAL
        self.entered_at_s = 0.0
        self.approach: str | None = None
        self._request: PriorityRequest | None = None

    def _transition(self, phase: SignalPhase, now_s: float) -> None:
        self.phase = phase
        self.entered_at_s = now_s

    def update(
        self,
        now_s: float,
        request: PriorityRequest | None = None,
        *,
        ev_passed: bool = False,
    ) -> SignalState:
        elapsed = now_s - self.entered_at_s
        if request is not None and request.expires_at > datetime.now(UTC):
            self._request = request
            self.approach = request.approach_id

        expired = self._request is not None and self._request.expires_at <= datetime.now(UTC)
        if self.phase == SignalPhase.NORMAL and self._request and not expired:
            self._transition(SignalPhase.REQUEST_VALID, now_s)
        elif self.phase == SignalPhase.REQUEST_VALID:
            self._transition(SignalPhase.PRE_CLEAR, now_s)
        elif self.phase == SignalPhase.PRE_CLEAR and elapsed >= self.timings.minimum_green_s:
            self._transition(SignalPhase.SAFE_TRANSITION, now_s)
        elif self.phase == SignalPhase.SAFE_TRANSITION and elapsed >= (
            self.timings.amber_s + self.timings.all_red_s
        ):
            self._transition(SignalPhase.EV_SERVICE, now_s)
        elif self.phase == SignalPhase.EV_SERVICE and (
            ev_passed or elapsed >= self.timings.maximum_preemption_s or expired
        ):
            self._transition(SignalPhase.EV_PASSED, now_s)
        elif self.phase == SignalPhase.EV_PASSED:
            self._transition(SignalPhase.RECOVERY, now_s)
        elif self.phase == SignalPhase.RECOVERY and elapsed >= self.timings.recovery_s:
            self._request = None
            self.approach = None
            self._transition(SignalPhase.NORMAL, now_s)

        seconds_to_change: float | None = None
        if self.phase == SignalPhase.PRE_CLEAR:
            seconds_to_change = max(0.0, self.timings.minimum_green_s - (now_s - self.entered_at_s))
        elif self.phase == SignalPhase.SAFE_TRANSITION:
            duration = self.timings.amber_s + self.timings.all_red_s
            seconds_to_change = max(0.0, duration - (now_s - self.entered_at_s))

        return SignalState(
            intersection_id=self.intersection_id,
            phase=self.phase,
            active_approach=self.approach,
            seconds_to_change=seconds_to_change,
            conflicting_green=False,
        )

