import pytest

from fusion import fuse_observations
from schema import RoadObservation, SourceKind


def observation(source: SourceKind, time: float, stddev: float, **extra: object) -> RoadObservation:
    values: dict[str, object] = dict(
        road_id="A2",
        source=source,
        travel_time_s=time,
        stddev_s=stddev,
        confidence=0.9,
    )
    values.update(extra)
    return RoadObservation.model_validate(values)


def test_lower_variance_observation_has_more_influence() -> None:
    estimate = fuse_observations(
        "A2",
        observation(SourceKind.MACRO, 40, 10),
        observation(SourceKind.PERCEPTION, 100, 2),
    )
    assert estimate.travel_time_s == pytest.approx(97.14, rel=0.02)
    assert estimate.blockage is False


def test_high_confidence_blockage_overrides_macro() -> None:
    estimate = fuse_observations(
        "A2",
        observation(SourceKind.MACRO, 40, 3),
        observation(SourceKind.PERCEPTION, 160, 5, blockage=True, confidence=0.91),
    )
    assert estimate.travel_time_s == 3600
    assert estimate.blockage is True


def test_requires_an_observation() -> None:
    with pytest.raises(ValueError, match="at least one"):
        fuse_observations("A2", None, None)
