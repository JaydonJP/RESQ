"""The decision brain: forecast -> fuse -> route -> signal, with no dependency
on perception or a macro feed. Those sources plug into the same
`fuse_observations` call later; today the brain runs on forecasting alone and
keeps deciding as long as at least one of the two forecasters is alive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from corridor import CorridorTimings, IntersectionController
from routing import should_switch_route
from schema import (
    ControlState,
    DecisionEvent,
    PriorityRequest,
    RoadEstimate,
    RouteOption,
    SignalState,
)
from sim.chennai.roads import IncidentPlan, RoadNetwork, demo_plan, point_along

from .forecasting import ForecastBrain
from .traffic_source import SyntheticTrafficSource

SIGNAL_CHECKPOINTS = (("TL-F1", 0.3), ("TL-F2", 0.6), ("TL-F3", 0.9))


def _edge_lengths(network: RoadNetwork, edge_ids: set[str]) -> dict[str, float]:
    lengths: dict[str, float] = {}
    for edges in network.adjacency.values():
        for edge in edges:
            if edge.edge_id in edge_ids:
                lengths[edge.edge_id] = edge.length_m
    return lengths


def _path_neighbours(edge_ids: tuple[str, ...]) -> dict[str, list[str]]:
    neighbours: dict[str, list[str]] = {edge_id: [] for edge_id in edge_ids}
    for index, edge_id in enumerate(edge_ids):
        if index > 0:
            neighbours[edge_id].append(edge_ids[index - 1])
        if index + 1 < len(edge_ids):
            neighbours[edge_id].append(edge_ids[index + 1])
    return neighbours


@dataclass
class DecisionOutput:
    roads: list[RoadEstimate]
    routes: list[RouteOption]
    signals: list[SignalState]
    decisions: list[DecisionEvent]
    vehicle_position: object
    vehicle_heading_deg: float
    vehicle_speed_mps: float
    selected_route_id: str
    progress: float
    overall_confidence: float
    active_sources: list[str] = field(default_factory=list)


class DecisionEngine:
    """Stateful brain for one vehicle mission. Ticked with wall/sim time; keeps
    hysteresis state for route selection and one IntersectionController per
    virtual signal checkpoint along the corridor."""

    def __init__(self, network: RoadNetwork | None = None, plan: IncidentPlan | None = None) -> None:
        self.network = network or RoadNetwork()
        self.plan = plan or demo_plan()

        edge_ids = set(self.plan.normal.edges) | set(self.plan.bypass.edges)
        self.edge_lengths_m = _edge_lengths(self.network, edge_ids)
        neighbours: dict[str, list[str]] = {}
        for path in (self.plan.normal, self.plan.bypass):
            for edge_id, adjacent in _path_neighbours(path.edges).items():
                neighbours.setdefault(edge_id, [])
                for item in adjacent:
                    if item not in neighbours[edge_id]:
                        neighbours[edge_id].append(item)

        # The stretch ResQ's bypass avoids is deliberately made congestion-prone
        # so the reroute decision is driven by the forecast, not a manual flag.
        congested = set(self.plan.blocked_edges) & set(self.plan.normal.edges)
        self.traffic = SyntheticTrafficSource(
            {edge_id: 8.5 for edge_id in edge_ids},
            congested_edges=congested,
        )
        self.forecast = ForecastBrain(self.edge_lengths_m, neighbours, self.traffic)

        self._selected_route_id = "route-a"
        self._controllers = {
            signal_id: IntersectionController(signal_id, CorridorTimings())
            for signal_id, _ in SIGNAL_CHECKPOINTS
        }

    def _road_estimates(self, now_s: float, controls: ControlState) -> dict[str, RoadEstimate]:
        edge_ids = list(self.edge_lengths_m)
        recent_speeds = {
            edge_id: self.traffic.recent_speeds(edge_id, now_s, controls.congestion_scenario)
            for edge_id in edge_ids
        }
        estimates: dict[str, RoadEstimate] = {}
        for edge_id in edge_ids:
            estimate = self.forecast.estimate(
                edge_id,
                now_s,
                recent_speeds,
                historical_enabled=controls.historical_model_enabled,
                spatial_temporal_enabled=controls.spatial_temporal_model_enabled,
            )
            if estimate is None:
                continue
            estimates[edge_id] = estimate
        return estimates

    @staticmethod
    def _path_eta(edge_ids: tuple[str, ...], estimates: dict[str, RoadEstimate], static_travel_s: dict[str, float]) -> float:
        return sum(
            estimates[edge_id].travel_time_s if edge_id in estimates else static_travel_s[edge_id]
            for edge_id in edge_ids
        )

    def tick(self, now_s: float, controls: ControlState) -> DecisionOutput:
        estimates = self._road_estimates(now_s, controls)

        # Static per-edge fallback: derive from the network directly so a road
        # with no live estimate still contributes a sane travel time.
        static_lookup: dict[str, float] = {}
        for edges in self.network.adjacency.values():
            for edge in edges:
                if edge.edge_id in self.edge_lengths_m:
                    static_lookup[edge.edge_id] = edge.travel_s

        normal_eta = self._path_eta(self.plan.normal.edges, estimates, static_lookup)
        bypass_eta = self._path_eta(self.plan.bypass.edges, estimates, static_lookup)
        etas = {"route-a": normal_eta, "route-b": bypass_eta}

        current_eta = etas[self._selected_route_id]
        other_route_id = "route-b" if self._selected_route_id == "route-a" else "route-a"
        candidate_eta = etas[other_route_id]
        switched = should_switch_route(current_eta, candidate_eta)
        decisions: list[DecisionEvent] = []
        if switched:
            decisions.append(
                DecisionEvent(
                    at_s=now_s,
                    kind="reroute",
                    message=(
                        f"Forecast-driven reroute: {other_route_id} saves "
                        f"{current_eta - candidate_eta:.0f}s over {self._selected_route_id}"
                    ),
                )
            )
            self._selected_route_id = other_route_id

        active_sources = sorted(
            {source for source in (
                "historical" if controls.historical_model_enabled else None,
                "spatial_temporal" if controls.spatial_temporal_model_enabled else None,
            ) if source}
        )
        if len(active_sources) < 2:
            decisions.append(
                DecisionEvent(
                    at_s=now_s,
                    kind="degraded",
                    message=(
                        f"Deciding on {active_sources[0]} forecast alone"
                        if active_sources
                        else "No forecasting model enabled: using last known static travel times"
                    ),
                )
            )

        path = self.plan.normal if self._selected_route_id == "route-a" else self.plan.bypass
        selected_eta = etas[self._selected_route_id]
        progress = min(1.0, (now_s % (selected_eta + 15)) / selected_eta) if selected_eta > 0 else 0.0
        position = point_along(path, progress)
        ahead = point_along(path, min(1.0, progress + 0.002))
        heading = _bearing(position, ahead)
        speed_mps = path.distance_m / path.travel_s if progress < 1 else 0.0

        roads = list(estimates.values())
        confidences = [estimate.confidence for estimate in roads]
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        routes = [
            RouteOption(
                route_id="route-a",
                label="Regular · via Avenue Road",
                edge_ids=list(self.plan.normal.edges),
                eta_s=normal_eta,
                selected=self._selected_route_id == "route-a",
                reason="Forecast-fused ETA is currently the fastest of the two mapped routes",
                geometry=list(self.plan.normal.geometry),
            ),
            RouteOption(
                route_id="route-b",
                label="ResQ · via Valluvar Kottam",
                edge_ids=list(self.plan.bypass.edges),
                eta_s=bypass_eta,
                selected=self._selected_route_id == "route-b",
                reason="Forecast-fused ETA shows the bypass beating the regular route by the hysteresis margin",
                geometry=list(self.plan.bypass.geometry),
            ),
        ]

        signals = self._signal_states(now_s, path, selected_eta, progress, overall_confidence)

        decisions.insert(
            0,
            DecisionEvent(
                at_s=now_s,
                kind="route",
                message=f"{self._selected_route_id} selected from {len(active_sources) or 0}-model forecast fusion",
            ),
        )

        return DecisionOutput(
            roads=roads,
            routes=routes,
            signals=signals,
            decisions=decisions,
            vehicle_position=position,
            vehicle_heading_deg=heading,
            vehicle_speed_mps=speed_mps,
            selected_route_id=self._selected_route_id,
            progress=progress,
            overall_confidence=overall_confidence,
            active_sources=active_sources,
        )

    def _signal_states(self, now_s, path, selected_eta, progress, confidence) -> list[SignalState]:
        elapsed_s = progress * selected_eta
        states: list[SignalState] = []
        for signal_id, fraction in SIGNAL_CHECKPOINTS:
            checkpoint_eta_s = fraction * selected_eta
            controller = self._controllers[signal_id]
            remaining = checkpoint_eta_s - elapsed_s
            passed = remaining <= 0
            request = None
            if not passed and remaining <= 45:
                request = PriorityRequest(
                    request_id=f"{signal_id}-{int(now_s)}",
                    vehicle_id="AMB-01",
                    intersection_id=signal_id,
                    approach_id="approach",
                    eta_s=max(0.0, remaining),
                    queue_pcu=4.0,
                    confidence=confidence,
                    expires_at=datetime.now(UTC) + timedelta(seconds=90),
                )
            states.append(controller.update(now_s, request, ev_passed=passed))
        return states


def _bearing(a, b) -> float:
    from math import atan2, cos, degrees, radians, sin

    y = sin(radians(b.lon - a.lon)) * cos(radians(b.lat))
    x = cos(radians(a.lat)) * sin(radians(b.lat)) - sin(radians(a.lat)) * cos(radians(b.lat)) * cos(
        radians(b.lon - a.lon)
    )
    return (degrees(atan2(y, x)) + 360) % 360
