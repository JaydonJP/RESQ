"""Confidence-aware road travel-time fusion."""

from dataclasses import dataclass
from math import sqrt

from schema import RoadEstimate, RoadObservation, SourceKind


@dataclass(frozen=True, slots=True)
class FusionConfig:
    blockage_confidence: float = 0.8
    near_closed_time_s: float = 3600.0
    macro_age_penalty_per_s: float = 0.02
    perception_distance_penalty_per_m: float = 0.004


def _adjusted_stddev(observation: RoadObservation, config: FusionConfig) -> float:
    if observation.source == SourceKind.MACRO:
        return observation.stddev_s * (1 + observation.age_s * config.macro_age_penalty_per_s)
    distance = observation.distance_m or 0
    confidence_penalty = 1 + (1 - observation.confidence)
    return observation.stddev_s * (
        1 + distance * config.perception_distance_penalty_per_m
    ) * confidence_penalty


def fuse_observations(
    road_id: str,
    macro: RoadObservation | None,
    perception: RoadObservation | None,
    config: FusionConfig | None = None,
) -> RoadEstimate:
    """Fuse macro and perception estimates using inverse-variance weighting."""

    config = config or FusionConfig()
    if macro is None and perception is None:
        raise ValueError("at least one observation is required")
    for observation in (macro, perception):
        if observation is not None and observation.road_id != road_id:
            raise ValueError("all observations must refer to the requested road")

    if (
        perception is not None
        and perception.blockage
        and perception.confidence >= config.blockage_confidence
    ):
        return RoadEstimate(
            road_id=road_id,
            travel_time_s=config.near_closed_time_s,
            confidence=perception.confidence,
            macro_time_s=macro.travel_time_s if macro else None,
            perception_time_s=perception.travel_time_s,
            blockage=True,
            explanation="Perception override: high-confidence blockage",
        )

    observations = [item for item in (macro, perception) if item is not None]
    adjusted = [(item, _adjusted_stddev(item, config)) for item in observations]
    precision_sum = sum(1 / (stddev**2) for _, stddev in adjusted)
    travel_time = sum(item.travel_time_s / (stddev**2) for item, stddev in adjusted)
    travel_time /= precision_sum
    combined_stddev = sqrt(1 / precision_sum)
    confidence = max(0.0, min(1.0, 1 - combined_stddev / max(travel_time, 1)))
    source_label = "macro + perception" if len(adjusted) == 2 else adjusted[0][0].source.value

    return RoadEstimate(
        road_id=road_id,
        travel_time_s=travel_time,
        confidence=confidence,
        macro_time_s=macro.travel_time_s if macro else None,
        perception_time_s=perception.travel_time_s if perception else None,
        blockage=False,
        explanation=f"Inverse-variance estimate from {source_label}",
    )

