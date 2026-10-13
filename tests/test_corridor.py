from datetime import UTC, datetime, timedelta

from corridor import CorridorTimings, IntersectionController
from schema import PriorityRequest, SignalPhase

BASE_TIME = datetime(2026, 10, 13, tzinfo=UTC)


def request(*, expires_at: datetime | None = None) -> PriorityRequest:
    return PriorityRequest(
        request_id="req-1",
        vehicle_id="AMB-01",
        intersection_id="TL-04",
        approach_id="eastbound",
        eta_s=12,
        queue_pcu=8,
        confidence=0.9,
        expires_at=expires_at or BASE_TIME + timedelta(minutes=1),
    )


def test_signal_sequence_preserves_safe_transition() -> None:
    controller = IntersectionController(
        "TL-04",
        CorridorTimings(minimum_green_s=2, amber_s=1, all_red_s=1, recovery_s=2),
    )
    def advance(seconds: float, request_value: PriorityRequest | None = None, **kwargs):
        return controller.update(
            seconds,
            request_value,
            now_at=BASE_TIME + timedelta(seconds=seconds),
            **kwargs,
        )

    states = [advance(0, request()).phase]
    states.append(advance(0.1).phase)
    states.append(advance(2.2).phase)
    states.append(advance(4.3).phase)
    states.append(advance(4.4, ev_passed=True).phase)
    states.append(advance(4.5).phase)
    states.append(advance(6.6).phase)

    assert states == [
        SignalPhase.REQUEST_VALID,
        SignalPhase.PRE_CLEAR,
        SignalPhase.SAFE_TRANSITION,
        SignalPhase.EV_SERVICE,
        SignalPhase.EV_PASSED,
        SignalPhase.RECOVERY,
        SignalPhase.NORMAL,
    ]
    assert advance(6.7).conflicting_green is None


def test_expiry_uses_the_supplied_clock() -> None:
    controller = IntersectionController("TL-04")
    expired = request(expires_at=BASE_TIME - timedelta(seconds=1))
    assert controller.update(0, expired, now_at=BASE_TIME).phase == SignalPhase.NORMAL
    future = request(expires_at=BASE_TIME + timedelta(seconds=1))
    assert controller.update(0, future, now_at=BASE_TIME).phase == SignalPhase.REQUEST_VALID
    assert controller.update(2, now_at=BASE_TIME + timedelta(seconds=2)).phase == SignalPhase.NORMAL


def test_conflict_flag_requires_a_measurement() -> None:
    controller = IntersectionController("TL-04")
    assert controller.update(0, now_at=BASE_TIME).conflicting_green is None
    assert controller.update(1, now_at=BASE_TIME, conflicting_green=True).conflicting_green is True

