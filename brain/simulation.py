"""Live-tickable wrapper around DecisionEngine, exposed to the API/web app."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from time import monotonic

from schema import ControlState, DataHealth, NetworkSnapshot, VehicleState

from .engine import DecisionEngine


class BrainSimulation:
    """Same shape as `sim.demo.DemoSimulation`, but driven end-to-end by real
    forecasting output through the fusion and decision engine instead of a
    staged/scripted scenario. Perception and a live macro feed are not wired
    in yet; the brain runs on whichever forecasting models are enabled and
    keeps deciding even if one of them is turned off or fails."""

    def __init__(self) -> None:
        self.controls = ControlState()
        self._engine = DecisionEngine()
        self._started_at = monotonic()

    def reset(self) -> None:
        self.controls = ControlState()
        self._engine = DecisionEngine()
        self._started_at = monotonic()

    def update_controls(self, **changes: bool | int) -> ControlState:
        current = self.controls.model_dump()
        unknown = set(changes) - set(current)
        if unknown:
            raise ValueError(f"unknown controls: {', '.join(sorted(unknown))}")
        current.update(changes)
        self.controls = ControlState.model_validate(current)
        return deepcopy(self.controls)

    def snapshot(self) -> NetworkSnapshot:
        sim_time = monotonic() - self._started_at
        output = self._engine.tick(sim_time, self.controls)

        return NetworkSnapshot(
            generated_at=datetime.now(UTC),
            sim_time_s=sim_time,
            scenario="forecast-brain",
            vehicle=VehicleState(
                vehicle_id="AMB-01",
                position=output.vehicle_position,
                speed_mps=output.vehicle_speed_mps,
                heading_deg=output.vehicle_heading_deg,
                route_id=output.selected_route_id,
                progress=output.progress,
            ),
            roads=output.roads,
            routes=output.routes,
            signals=output.signals,
            decisions=output.decisions,
            controls=self.controls,
            health=DataHealth(
                macro_age_s=0.0,
                perception_online=False,
                overall_confidence=output.overall_confidence,
            ),
            incident=None,
        )
