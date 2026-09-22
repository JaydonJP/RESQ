"""Sensor-agnostic tracking, queue, blockage, and short-horizon prediction."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from schema import RoadObservation, SourceKind


@dataclass(frozen=True, slots=True)
class TrackedObject:
    track_id: str
    class_name: str
    lane_id: str
    distance_m: float
    lateral_m: float
    speed_mps: float
    stopped_for_s: float
    confidence: float


@dataclass(frozen=True, slots=True)
class PredictedTrack:
    track_id: str
    horizon_s: float
    distance_m: float
    gap_opening: bool


def predict_tracks(tracks: list[TrackedObject], horizon_s: float = 2) -> list[PredictedTrack]:
    return [
        PredictedTrack(
            track_id=track.track_id,
            horizon_s=horizon_s,
            distance_m=max(0, track.distance_m - track.speed_mps * horizon_s),
            gap_opening=track.speed_mps >= 2.5 and track.lateral_m > 1.2,
        )
        for track in tracks
    ]


class BlockageDetector:
    def __init__(self, minimum_stopped: int = 3, stopped_threshold_s: float = 3) -> None:
        self.minimum_stopped = minimum_stopped
        self.stopped_threshold_s = stopped_threshold_s

    def observe(self, road_id: str, tracks: list[TrackedObject]) -> RoadObservation:
        stopped = [track for track in tracks if track.stopped_for_s >= self.stopped_threshold_s]
        lanes = {track.lane_id for track in stopped}
        blockage = len(stopped) >= self.minimum_stopped and len(lanes) >= 2
        confidence = 0.35 if not tracks else sum(item.confidence for item in tracks) / len(tracks)
        queue_tail = max((track.distance_m for track in stopped), default=0)
        queue_delay = len(stopped) * 2.2 + queue_tail / 6
        return RoadObservation(
            road_id=road_id,
            source=SourceKind.PERCEPTION,
            travel_time_s=max(5, 18 + queue_delay),
            stddev_s=max(2, 8 * (1 - confidence)),
            confidence=confidence,
            distance_m=queue_tail,
            blockage=blockage,
        )


def cluster_lidar(
    points: list[tuple[float, float, float]], radius_m: float = 1.5, minimum_points: int = 3
) -> list[list[tuple[float, float, float]]]:
    """Small deterministic Euclidean clusterer for a filtered ground-plane cloud."""

    remaining = set(range(len(points)))
    clusters: list[list[tuple[float, float, float]]] = []
    while remaining:
        seed = remaining.pop()
        cluster_indexes = {seed}
        frontier = [seed]
        while frontier:
            current = frontier.pop()
            x1, y1, _ = points[current]
            neighbours = {
                index
                for index in remaining
                if hypot(points[index][0] - x1, points[index][1] - y1) <= radius_m
            }
            remaining -= neighbours
            cluster_indexes |= neighbours
            frontier.extend(neighbours)
        if len(cluster_indexes) >= minimum_points:
            clusters.append([points[index] for index in sorted(cluster_indexes)])
    return clusters
