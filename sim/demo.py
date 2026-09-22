"""Road-network-backed, deterministic review demonstration."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from math import atan2, cos, degrees, radians, sin
from time import monotonic

from fusion import fuse_observations
from routing import should_switch_route
from schema import (
    ControlState,
    DataHealth,
    DecisionEvent,
    NetworkSnapshot,
    RoadEstimate,
    RoadObservation,
    RouteOption,
    SignalPhase,
    SignalState,
    SourceKind,
    VehicleState,
)
from sim.chennai.roads import demo_plan, point_along

# Staged inputs, not empirical performance measurements.
INCIDENT_QUEUE_S = 120.0
RESQ_CUE_S = 8.0


def _heading(path, progress: float) -> float:
    current = point_along(path, progress)
    ahead = point_along(path, min(1.0, progress + 0.002))
    y = sin(radians(ahead.lon - current.lon)) * cos(radians(ahead.lat))
    x = cos(radians(current.lat)) * sin(radians(ahead.lat)) - sin(radians(current.lat)) * cos(
        radians(ahead.lat)
    ) * cos(radians(ahead.lon - current.lon))
    return (degrees(atan2(y, x)) + 360) % 360


class DemoSimulation:
    def __init__(self) -> None:
        self.controls = ControlState()
        self._started_at = monotonic()

    def reset(self) -> None:
        self.controls = ControlState()
        self._started_at = monotonic()

    def update_controls(self, **changes: bool | int) -> ControlState:
        current = self.controls.model_dump()
        unknown = set(changes) - set(current)
        if unknown:
            raise ValueError(f"unknown controls: {', '.join(sorted(unknown))}")
        current.update(changes)
        self.controls = ControlState.model_validate(current)
        # Each control change starts a new staged run, avoiding a jump between roads.
        self._started_at = monotonic()
        return deepcopy(self.controls)

    def _road_estimates(self) -> list[RoadEstimate]:
        adoption_penalty = max(0, 30 - self.controls.adoption_percent) / 10
        base = {"A1": 32.0, "A2": 38.0, "A3": 27.0, "B1": 39.0, "B2": 42.0, "B3": 37.0}
        estimates: list[RoadEstimate] = []
        for road_id, travel_time in base.items():
            # An offline feed retains a stale last-known observation. That is a
            # demo fallback; an empty sensor set must not crash the live socket.
            macro = RoadObservation(
                road_id=road_id,
                source=SourceKind.MACRO,
                travel_time_s=travel_time,
                stddev_s=3.0 + adoption_penalty,
                confidence=0.88 - adoption_penalty * 0.08,
                age_s=4.0 if self.controls.macro_feed else 180.0,
            )
            perception = None
            if road_id == "A2" and self.controls.camera:
                perception = RoadObservation(
                    road_id=road_id,
                    source=SourceKind.PERCEPTION,
                    travel_time_s=210.0 if self.controls.accident else 40.0,
                    stddev_s=5.0,
                    confidence=0.93,
                    distance_m=118.0,
                    blockage=self.controls.accident,
                )
            estimates.append(fuse_observations(road_id, macro, perception))
        return estimates

    def snapshot(self) -> NetworkSnapshot:
        plan = demo_plan()
        sim_time = monotonic() - self._started_at
        roads = self._road_estimates()
        accident_visible = self.controls.accident and self.controls.camera
        normal_eta = plan.normal.travel_s + (INCIDENT_QUEUE_S if accident_visible else 0)
        bypass_eta = plan.bypass.travel_s + RESQ_CUE_S
        selected = (
            "route-b"
            if accident_visible and should_switch_route(normal_eta, bypass_eta)
            else "route-a"
        )
        path = plan.bypass if selected == "route-b" else plan.normal
        selected_eta = bypass_eta if selected == "route-b" else normal_eta
        progress = min(1.0, (sim_time % (selected_eta + 15)) / selected_eta)

        routes = [
            RouteOption(
                route_id="route-a",
                label="Regular · via Avenue Road",
                edge_ids=list(plan.normal.edges),
                eta_s=normal_eta,
                selected=selected == "route-a",
                reason="Shortest mapped route; staged queue is hidden from the regular ambulance"
                if self.controls.accident
                else "Shortest route on mapped drivable roads",
                geometry=list(plan.normal.geometry),
            ),
            RouteOption(
                route_id="route-b",
                label="ResQ · via Valluvar Kottam",
                edge_ids=list(plan.bypass.edges),
                eta_s=bypass_eta,
                selected=selected == "route-b",
                reason="Road-graph bypass of the staged incident; 8 s detection/decision allowance",
                geometry=list(plan.bypass.geometry),
            ),
        ]
        decisions = [
            DecisionEvent(
                at_s=0,
                kind="route",
                message="Shortest drivable route selected from the local OSM graph",
            )
        ]
        if self.controls.accident:
            decisions.append(
                DecisionEvent(
                    at_s=0,
                    kind="reroute" if accident_visible else "warning",
                    message="Staged incident cue: ResQ takes the connected bypass"
                    if accident_visible
                    else "Incident is hidden while camera input is unavailable",
                )
            )
        signals = [
            SignalState(
                intersection_id=signal_id,
                phase=SignalPhase.PRE_CLEAR if index == 0 else SignalPhase.REQUEST_VALID,
                active_approach="northbound" if selected == "route-b" else "eastbound",
                seconds_to_change=max(0, 4 - index),
                conflicting_green=False,
            )
            for index, signal_id in enumerate(("TL-04", "TL-07", "TL-11"))
        ]
        confidence = (0.91 if self.controls.camera else 0.58) - (
            0.18 if not self.controls.macro_feed else 0
        )
        return NetworkSnapshot(
            generated_at=datetime.now(UTC),
            sim_time_s=sim_time,
            scenario="staged-hidden-incident",
            vehicle=VehicleState(
                vehicle_id="AMB-01",
                position=point_along(path, progress),
                speed_mps=path.distance_m / path.travel_s if progress < 1 else 0,
                heading_deg=_heading(path, progress),
                route_id=selected,
                progress=progress,
            ),
            roads=roads,
            routes=routes,
            signals=signals,
            decisions=decisions,
            controls=self.controls,
            health=DataHealth(
                macro_age_s=4.0 if self.controls.macro_feed else 180.0,
                perception_online=self.controls.camera,
                overall_confidence=max(0, confidence),
            ),
            incident=plan.incident,
        )
