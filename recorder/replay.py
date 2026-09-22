"""A transparent, deterministic route comparison for the project review.

This is not a trained-model result or a SUMO run. Both vehicles follow real OSM
road geometry; the incident dwell and early cue are explicit assumptions.
"""

from schema import (
    BaselineId,
    GhostReplay,
    ReplayFrame,
    ReplayVehicle,
    RouteOption,
    RunMetrics,
    ScenarioName,
)
from sim.chennai.roads import demo_plan, distance_m, point_along
from sim.demo import INCIDENT_QUEUE_S, RESQ_CUE_S


def build_ghost_replay(seed: int = 7) -> GhostReplay:
    plan = demo_plan()
    normal, bypass = plan.normal, plan.bypass
    baseline_time = normal.travel_s + INCIDENT_QUEUE_S
    resq_time = bypass.travel_s + RESQ_CUE_S
    incident_index = normal.geometry.index(plan.incident)
    incident_distance = sum(
        distance_m(a, b)
        for a, b in zip(
            normal.geometry[:incident_index], normal.geometry[1 : incident_index + 1], strict=True
        )
    )
    incident_progress = incident_distance / normal.distance_m
    incident_arrival_s = normal.travel_s * incident_progress

    metrics = [
        RunMetrics(
            run_id=f"staged-regular-{seed}",
            baseline=BaselineId.B0,
            scenario=ScenarioName.HIDDEN_ACCIDENT,
            seed=seed,
            ambulance_travel_time_s=baseline_time,
            stops=1,
            route_switches=0,
            green_on_arrival_rate=0,
            cross_traffic_added_delay_s=0,
            recovery_time_s=0,
            reroute_reaction_time_s=None,
            route_regret_s=max(0, baseline_time - resq_time),
        ),
        RunMetrics(
            run_id=f"staged-resq-{seed}",
            baseline=BaselineId.B5,
            scenario=ScenarioName.HIDDEN_ACCIDENT,
            seed=seed,
            ambulance_travel_time_s=resq_time,
            stops=0,
            route_switches=1,
            green_on_arrival_rate=0,
            cross_traffic_added_delay_s=0,
            recovery_time_s=0,
            reroute_reaction_time_s=RESQ_CUE_S,
            route_regret_s=0,
        ),
    ]

    duration = baseline_time
    frames: list[ReplayFrame] = []
    for second in range(0, int(duration) + 3, 2):
        t = min(float(second), duration)
        if t < incident_arrival_s:
            regular_progress = t / normal.travel_s
        elif t < incident_arrival_s + INCIDENT_QUEUE_S:
            regular_progress = incident_progress
        else:
            regular_progress = min(1.0, (t - INCIDENT_QUEUE_S) / normal.travel_s)
        resq_progress = min(1.0, max(0.0, (t - RESQ_CUE_S) / bypass.travel_s))
        event = None
        if second == 0:
            event = "Same start and destination. ResQ receives a staged incident cue."
        elif second == int(RESQ_CUE_S):
            event = "ResQ takes the connected road-network bypass."
        elif second == 2 * round(incident_arrival_s / 2):
            event = "Regular ambulance reaches the incident queue and waits 120 s."
        elif second == 2 * round((incident_arrival_s + INCIDENT_QUEUE_S) / 2):
            event = "The queue clears; the regular ambulance continues."
        elif second == 2 * round(resq_time / 2):
            event = "ResQ arrives at the hospital in this assumed scenario."
        elif incident_arrival_s <= t < incident_arrival_s + INCIDENT_QUEUE_S:
            remaining = round(incident_arrival_s + INCIDENT_QUEUE_S - t)
            event = f"Regular ambulance waits at the staged incident ({remaining} s remaining)."
        elif t >= resq_time:
            event = "ResQ has arrived; the regular ambulance is still en route."
        frames.append(
            ReplayFrame(
                t_s=t,
                event=event,
                vehicles=[
                    ReplayVehicle(
                        baseline=BaselineId.B0,
                        position=point_along(normal, regular_progress),
                        progress=regular_progress,
                        arrived=t >= baseline_time,
                    ),
                    ReplayVehicle(
                        baseline=BaselineId.B5,
                        position=point_along(bypass, resq_progress),
                        progress=resq_progress,
                        arrived=t >= resq_time,
                    ),
                ],
            )
        )

    return GhostReplay(
        replay_id=f"staged-incident-{seed}",
        scenario=ScenarioName.HIDDEN_ACCIDENT,
        seed=seed,
        duration_s=duration,
        routes=[
            RouteOption(
                route_id="route-a",
                label="Regular ambulance · Avenue Road",
                edge_ids=list(normal.edges),
                eta_s=baseline_time,
                selected=False,
                reason="Shortest road route plus assumed 120 s incident queue",
                geometry=list(normal.geometry),
            ),
            RouteOption(
                route_id="route-b",
                label="ResQ demonstration · Valluvar Kottam",
                edge_ids=list(bypass.edges),
                eta_s=resq_time,
                selected=True,
                reason="Connected bypass plus assumed 8 s incident-cue allowance",
                geometry=list(bypass.geometry),
            ),
        ],
        frames=frames,
        metrics=metrics,
        origin=plan.origin,
        hospital=plan.hospital,
        incident=plan.incident,
        assumptions=[
            "OpenStreetMap road geometry; shortest-time routing with mapped one-way streets.",
            "Assumed driving speeds: 8.5 m/s on roads, 5.5 m/s on service roads.",
            "Regular route waits 120 s at a staged incident; ResQ gets an incident cue after 8 s.",
            "No real telemetry, trained-model inference, live signal actuation, "
            "or SUMO traffic is used.",
        ],
        demonstration_only=True,
    )
