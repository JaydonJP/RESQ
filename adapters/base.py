"""Interfaces shared by real and simulated data sources."""

from typing import Protocol

from schema import NetworkSnapshot


class AdapterUnavailable(RuntimeError):
    pass


class SimulationAdapter(Protocol):
    def start(self) -> None: ...

    def step(self) -> NetworkSnapshot: ...

    def close(self) -> None: ...
