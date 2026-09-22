"""Optional SUMO/TraCI bridge using the same interface as the fast adapter."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from .base import AdapterUnavailable


class SumoTraCIAdapter:
    def __init__(self, config_path: str | Path, *, gui: bool = False, label: str = "resq") -> None:
        self.config_path = Path(config_path)
        self.gui = gui
        self.label = label
        self._traci: Any = None

    @property
    def available(self) -> bool:
        return importlib.util.find_spec("traci") is not None

    def start(self) -> None:
        if not self.available:
            raise AdapterUnavailable("TraCI is unavailable; install SUMO and its Python tools")
        if not self.config_path.exists():
            raise AdapterUnavailable(f"SUMO config not found: {self.config_path}")
        traci = importlib.import_module("traci")
        traci.start(
            ["sumo-gui" if self.gui else "sumo", "-c", str(self.config_path), "--start"],
            label=self.label,
        )
        self._traci = traci.getConnection(self.label)

    def step(self, target_time_s: float | None = None) -> dict[str, object]:
        if self._traci is None:
            raise AdapterUnavailable("SUMO adapter has not been started")
        self._traci.simulationStep(target_time_s or 0)
        vehicles = [
            {
                "vehicle_id": vehicle_id,
                "road_id": self._traci.vehicle.getRoadID(vehicle_id),
                "position": self._traci.vehicle.getPosition(vehicle_id),
                "speed_mps": self._traci.vehicle.getSpeed(vehicle_id),
                "next_tls": self._traci.vehicle.getNextTLS(vehicle_id),
            }
            for vehicle_id in self._traci.vehicle.getIDList()
        ]
        return {
            "time_s": self._traci.simulation.getTime(),
            "vehicles": vehicles,
            "traffic_lights": list(self._traci.trafficlight.getIDList()),
        }

    def set_signal_phase(self, signal_id: str, phase_index: int) -> None:
        if self._traci is None:
            raise AdapterUnavailable("SUMO adapter has not been started")
        self._traci.trafficlight.setPhase(signal_id, phase_index)

    def close(self) -> None:
        if self._traci is not None:
            self._traci.close()
            self._traci = None
