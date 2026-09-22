"""Explainable forecasting baselines used before GPU graph models are introduced."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import fmean


@dataclass(frozen=True, slots=True)
class SpeedRecord:
    road_id: str
    minute_of_week: int
    speed_mps: float


@dataclass(frozen=True, slots=True)
class SpeedForecast:
    road_id: str
    horizon_minutes: int
    speed_mps: float
    stddev_mps: float


class HistoricalAverageForecaster:
    def __init__(self, bucket_minutes: int = 15) -> None:
        self.bucket_minutes = bucket_minutes
        self._values: dict[tuple[str, int], list[float]] = defaultdict(list)
        self._road_values: dict[str, list[float]] = defaultdict(list)

    def fit(self, records: list[SpeedRecord]) -> HistoricalAverageForecaster:
        self._values.clear()
        self._road_values.clear()
        for record in records:
            bucket = record.minute_of_week // self.bucket_minutes
            self._values[(record.road_id, bucket)].append(record.speed_mps)
            self._road_values[record.road_id].append(record.speed_mps)
        return self

    def predict(self, road_id: str, minute_of_week: int, horizon_minutes: int) -> SpeedForecast:
        target = minute_of_week + horizon_minutes
        bucket = target // self.bucket_minutes
        values = self._values.get((road_id, bucket)) or self._road_values.get(road_id)
        if not values:
            raise ValueError(f"no history for road {road_id!r}")
        mean = fmean(values)
        variance = fmean((value - mean) ** 2 for value in values)
        return SpeedForecast(road_id, horizon_minutes, mean, variance**0.5)


class SpatialTemporalForecaster:
    """Graph-smoothed autoregressive baseline with no training dependency."""

    def __init__(self, neighbours: dict[str, list[str]], persistence: float = 0.72) -> None:
        self.neighbours = neighbours
        self.persistence = persistence

    def predict(
        self,
        recent_speeds: dict[str, list[float]],
        road_id: str,
        horizons: tuple[int, ...] = (5, 15, 30),
    ) -> list[SpeedForecast]:
        history = recent_speeds.get(road_id)
        if not history:
            raise ValueError(f"no recent values for road {road_id!r}")
        current = history[-1]
        own_trend = 0 if len(history) < 2 else history[-1] - history[-2]
        neighbour_values = [
            recent_speeds[item][-1]
            for item in self.neighbours.get(road_id, [])
            if recent_speeds.get(item)
        ]
        spatial = fmean(neighbour_values) if neighbour_values else current
        output: list[SpeedForecast] = []
        for horizon in horizons:
            steps = horizon / 5
            persistence = self.persistence**steps
            trend = own_trend * min(steps, 3)
            prediction = persistence * (current + trend) + (1 - persistence) * spatial
            output.append(
                SpeedForecast(
                    road_id=road_id,
                    horizon_minutes=horizon,
                    speed_mps=max(0.5, prediction),
                    stddev_mps=1.5 + horizon * 0.12,
                )
            )
        return output
