"""External-system adapters (SUMO, CARLA, and Google Routes live here)."""

from .base import AdapterUnavailable, SimulationAdapter
from .carla_sensors import CarlaSensorRig
from .google_routes import GoogleRoute, GoogleRoutesAdapter
from .sumo_traci import SumoTraCIAdapter

__all__ = [
    "AdapterUnavailable",
    "CarlaSensorRig",
    "GoogleRoute",
    "GoogleRoutesAdapter",
    "SimulationAdapter",
    "SumoTraCIAdapter",
]
