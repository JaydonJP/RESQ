from datetime import UTC, datetime, timedelta

from corridor import CorridorTimings, IntersectionController
from schema import PriorityRequest, SignalPhase


def request() -> PriorityRequest:
    return PriorityRequest(
        request_id="req-1",
        vehicle_id="AMB-01",
        intersection_id="TL-04",
        approach_id="eastbound",
        eta_s=12,
        queue_pcu=8,
        confidence=0.9,
        expires_at=datetime.now(UTC) + timedelta(minutes=1),
    )


def test_signal_sequence_preserves_safe_transition() -> None:
    controller = IntersectionController(
        "TL-04",
        CorridorTimings(minimum_green_s=2, amber_s=1, all_red_s=1, recovery_s=2),
    )
    states = [controller.update(0, request()).phase]
    states.append(controller.update(0.1).phase)
    states.append(controller.update(2.2).phase)
    states.append(controller.update(4.3).phase)
    states.append(controller.update(4.4, ev_passed=True).phase)
    states.append(controller.update(4.5).phase)
    states.append(controller.update(6.6).phase)

    assert states == [
        SignalPhase.REQUEST_VALID,
        SignalPhase.PRE_CLEAR,
        SignalPhase.SAFE_TRANSITION,
        SignalPhase.EV_SERVICE,
        SignalPhase.EV_PASSED,
        SignalPhase.RECOVERY,
        SignalPhase.NORMAL,
    ]
    assert controller.update(6.7).conflicting_green is False

