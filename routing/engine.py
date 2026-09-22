"""Small time-dependent routing core, independent of SUMO and OSMnx."""

from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from heapq import heappop, heappush
from math import inf


@dataclass(frozen=True, slots=True)
class RoadEdge:
    edge_id: str
    source: str
    target: str
    base_travel_time_s: float


@dataclass(frozen=True, slots=True)
class PathResult:
    edge_ids: tuple[str, ...]
    travel_time_s: float


EdgeCost = Callable[[RoadEdge, float], float]


class RouteGraph:
    def __init__(self, edges: Iterable[RoadEdge]) -> None:
        self._adjacency: dict[str, list[RoadEdge]] = defaultdict(list)
        for edge in edges:
            if edge.base_travel_time_s <= 0:
                raise ValueError("edge travel time must be positive")
            self._adjacency[edge.source].append(edge)

    def shortest_path(
        self,
        start: str,
        goal: str,
        departure_time_s: float = 0,
        edge_cost: EdgeCost | None = None,
    ) -> PathResult:
        """Dijkstra search where edge cost may depend on edge-entry time."""

        cost_fn = edge_cost or (lambda edge, _: edge.base_travel_time_s)
        best: dict[str, float] = {start: 0.0}
        previous: dict[str, tuple[str, str]] = {}
        queue: list[tuple[float, str]] = [(0.0, start)]

        while queue:
            elapsed, node = heappop(queue)
            if elapsed > best.get(node, inf):
                continue
            if node == goal:
                edge_ids: list[str] = []
                current = node
                while current != start:
                    parent, edge_id = previous[current]
                    edge_ids.append(edge_id)
                    current = parent
                edge_ids.reverse()
                return PathResult(tuple(edge_ids), elapsed)
            for edge in self._adjacency.get(node, []):
                travel_time = cost_fn(edge, departure_time_s + elapsed)
                if travel_time <= 0:
                    raise ValueError("edge cost must be positive")
                candidate = elapsed + travel_time
                if candidate < best.get(edge.target, inf):
                    best[edge.target] = candidate
                    previous[edge.target] = (node, edge.edge_id)
                    heappush(queue, (candidate, edge.target))

        raise ValueError(f"no route from {start!r} to {goal!r}")


def should_switch_route(
    current_eta_s: float,
    candidate_eta_s: float,
    minimum_saving_s: float = 10.0,
    minimum_saving_fraction: float = 0.05,
) -> bool:
    saving = current_eta_s - candidate_eta_s
    return saving >= minimum_saving_s and saving / current_eta_s >= minimum_saving_fraction

