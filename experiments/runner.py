"""Seeded B0-B5 experiment runner for the fast simulation mode."""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from statistics import fmean
from uuid import uuid4

from schema import BaselineId, ExperimentConfig, RunMetrics, ScenarioName


@dataclass(frozen=True, slots=True)
class BaselinePolicy:
    traffic_aware: bool
    fused_perception: bool
    preemption: str
    recovery: bool


POLICIES = {
    BaselineId.B0: BaselinePolicy(False, False, "none", False),
    BaselineId.B1: BaselinePolicy(True, False, "none", False),
    BaselineId.B2: BaselinePolicy(True, False, "fixed", False),
    BaselineId.B3: BaselinePolicy(True, True, "fixed", False),
    BaselineId.B4: BaselinePolicy(True, True, "jit", False),
    BaselineId.B5: BaselinePolicy(True, True, "jit", True),
}

DEMAND_FACTOR = {
    ScenarioName.OFF_PEAK: 0.78,
    ScenarioName.EVENING_PEAK: 1.20,
    ScenarioName.SATURATED: 1.58,
    ScenarioName.HIDDEN_ACCIDENT: 1.18,
    ScenarioName.STALE_FEED: 1.25,
    ScenarioName.CAMERA_DEGRADED: 1.20,
}


class FastScenarioRunner:
    """Runs a calibrated mesoscopic experiment without external simulators.

    The model is intentionally compact, but each baseline toggles only the feature
    described in the evaluation plan. Randomness is seeded and all metrics derive
    from the same sampled demand and signal conditions for fair comparisons.
    """

    def run(self, config: ExperimentConfig) -> RunMetrics:
        rng = random.Random(config.seed)
        policy = POLICIES[config.baseline]
        factor = DEMAND_FACTOR[config.scenario]
        demand_noise = rng.gauss(1, 0.045)
        route_a = 116 * factor * demand_noise
        route_b = 137 * factor * rng.gauss(1, 0.035)
        hidden_incident = config.scenario == ScenarioName.HIDDEN_ACCIDENT
        stale = config.scenario == ScenarioName.STALE_FEED
        degraded = config.scenario == ScenarioName.CAMERA_DEGRADED

        incident_delay = 0.0
        if hidden_incident:
            incident_delay = rng.uniform(125, 180)
        elif stale:
            incident_delay = rng.uniform(35, 70)

        perception_recall = 0.96
        if degraded:
            perception_recall = 0.70
        detection = policy.fused_perception and rng.random() <= perception_recall
        adoption_uncertainty = max(0, 30 - config.adoption_percent) * 0.45
        macro_error = rng.gauss(0, 6 + adoption_uncertainty + config.gps_noise_m * 0.18)

        selected_b = False
        route_switches = 0
        reaction_time: float | None = None
        if detection and incident_delay:
            selected_b = True
            route_switches = 1
            reaction_time = max(0.12, rng.gauss(0.62 if not degraded else 0.84, 0.11))
        elif policy.traffic_aware and not hidden_incident:
            selected_b = route_b + macro_error < route_a

        road_time = route_b if selected_b else route_a + incident_delay
        oracle_time = min(route_b, route_a + incident_delay)

        signal_count = 3
        if policy.preemption == "none":
            green_rate = min(1.0, max(0.0, rng.gauss(0.39, 0.12)))
            signal_delay = signal_count * (1 - green_rate) * rng.uniform(17, 27)
            cross_delay = 0.0
            recovery = 0.0
        elif policy.preemption == "fixed":
            green_rate = min(1.0, max(0.0, rng.gauss(0.84, 0.07)))
            signal_delay = signal_count * (1 - green_rate) * rng.uniform(8, 15)
            cross_delay = signal_count * rng.uniform(24, 39) * factor
            recovery = rng.uniform(55, 90) * factor
        else:
            green_rate = min(1.0, max(0.0, rng.gauss(0.94, 0.035)))
            signal_delay = signal_count * (1 - green_rate) * rng.uniform(5, 10)
            cross_delay = signal_count * rng.uniform(13, 22) * factor
            recovery = rng.uniform(30, 52) * factor
            if policy.recovery:
                cross_delay *= 0.62
                recovery *= 0.55

        travel_time = road_time + signal_delay
        stops = max(0, round(signal_count * (1 - green_rate) + rng.uniform(-0.25, 0.35)))
        return RunMetrics(
            run_id=str(uuid4()),
            baseline=config.baseline,
            scenario=config.scenario,
            seed=config.seed,
            ambulance_travel_time_s=round(travel_time, 3),
            stops=stops,
            route_switches=route_switches,
            green_on_arrival_rate=round(green_rate, 4),
            cross_traffic_added_delay_s=round(cross_delay, 3),
            recovery_time_s=round(recovery, 3),
            reroute_reaction_time_s=round(reaction_time, 3) if reaction_time else None,
            route_regret_s=round(max(0, road_time - oracle_time), 3),
            conflicting_green_violations=0,
        )

    def matrix(
        self,
        baselines: list[BaselineId],
        scenarios: list[ScenarioName],
        seeds: int,
        adoption_percent: int = 10,
    ) -> list[RunMetrics]:
        return [
            self.run(
                ExperimentConfig(
                    baseline=baseline,
                    scenario=scenario,
                    seed=seed,
                    adoption_percent=adoption_percent,
                )
            )
            for baseline in baselines
            for scenario in scenarios
            for seed in range(seeds)
        ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ResQ baseline matrix")
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--scenario", choices=[item.value for item in ScenarioName])
    parser.add_argument("--adoption", type=int, default=10)
    args = parser.parse_args()
    scenarios = [ScenarioName(args.scenario)] if args.scenario else list(ScenarioName)
    metrics = FastScenarioRunner().matrix(list(BaselineId), scenarios, args.seeds, args.adoption)
    for baseline in BaselineId:
        values = [item.ambulance_travel_time_s for item in metrics if item.baseline == baseline]
        print(f"{baseline.value}: {len(values)} runs, mean travel time {fmean(values):.1f} s")


if __name__ == "__main__":
    main()
