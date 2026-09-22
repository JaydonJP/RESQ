"""Crowd-GPS probe generation and robust per-road aggregation."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from hashlib import sha256
from statistics import median


@dataclass(frozen=True, slots=True)
class VehicleTruth:
    vehicle_id: str
    road_id: str
    lat: float
    lon: float
    speed_mps: float


@dataclass(frozen=True, slots=True)
class ProbeSample:
    device_id: str
    vehicle_id: str
    road_id: str
    lat: float
    lon: float
    speed_mps: float
    age_s: float


@dataclass(frozen=True, slots=True)
class AggregatedRoadSpeed:
    road_id: str
    speed_mps: float
    sample_count: int
    estimated_vehicle_count: float
    stddev_mps: float


class ProbeGenerator:
    def __init__(
        self,
        adoption_percent: int = 10,
        gps_noise_m: float = 10,
        dropout_rate: float = 0.08,
        maximum_lag_s: float = 5,
        seed: int = 0,
    ) -> None:
        if not 0 < adoption_percent <= 100:
            raise ValueError("adoption_percent must be in 1..100")
        self.adoption_percent = adoption_percent
        self.gps_noise_m = gps_noise_m
        self.dropout_rate = dropout_rate
        self.maximum_lag_s = maximum_lag_s
        self._random = random.Random(seed)

    def emit(self, vehicles: list[VehicleTruth]) -> list[ProbeSample]:
        output: list[ProbeSample] = []
        for vehicle in vehicles:
            digest = sha256(vehicle.vehicle_id.encode()).digest()
            stable_bucket = int.from_bytes(digest[:4], "big") % 100
            if stable_bucket >= self.adoption_percent or self._random.random() < self.dropout_rate:
                continue
            lat_noise = self._random.gauss(0, self.gps_noise_m) / 111_111
            lon_scale = max(0.2, math.cos(math.radians(vehicle.lat)))
            lon_noise = self._random.gauss(0, self.gps_noise_m) / (111_111 * lon_scale)
            speed_noise = self._random.gauss(0, max(0.35, vehicle.speed_mps * 0.04))
            output.append(
                ProbeSample(
                    device_id=f"probe-{vehicle.vehicle_id}",
                    vehicle_id=vehicle.vehicle_id,
                    road_id=vehicle.road_id,
                    lat=vehicle.lat + lat_noise,
                    lon=vehicle.lon + lon_noise,
                    speed_mps=max(0, vehicle.speed_mps + speed_noise),
                    age_s=self._random.uniform(0, self.maximum_lag_s),
                )
            )
        return output


class ProbeAggregator:
    def __init__(self, adoption_percent: int) -> None:
        if not 0 < adoption_percent <= 100:
            raise ValueError("adoption_percent must be in 1..100")
        self.adoption_rate = adoption_percent / 100

    def aggregate(self, samples: list[ProbeSample]) -> list[AggregatedRoadSpeed]:
        grouped: dict[str, dict[str, ProbeSample]] = {}
        for sample in samples:
            if sample.speed_mps < 2.2 or sample.speed_mps > 60:
                continue
            grouped.setdefault(sample.road_id, {})[sample.vehicle_id] = sample
        output: list[AggregatedRoadSpeed] = []
        for road_id, by_vehicle in sorted(grouped.items()):
            speeds = [sample.speed_mps for sample in by_vehicle.values()]
            centre = median(speeds)
            deviations = [abs(speed - centre) for speed in speeds]
            mad = median(deviations) if deviations else 0
            accepted = [
                speed for speed in speeds if mad == 0 or abs(speed - centre) <= max(1.5, 3 * mad)
            ]
            mean = sum(accepted) / len(accepted)
            variance = sum((speed - mean) ** 2 for speed in accepted) / len(accepted)
            output.append(
                AggregatedRoadSpeed(
                    road_id=road_id,
                    speed_mps=mean,
                    sample_count=len(accepted),
                    estimated_vehicle_count=len(accepted) / self.adoption_rate,
                    stddev_mps=math.sqrt(variance),
                )
            )
        return output
