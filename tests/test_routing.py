import pytest

from routing import RoadEdge, RouteGraph, should_switch_route


def test_time_dependent_cost_can_change_selected_route() -> None:
    graph = RouteGraph(
        [
            RoadEdge("A1", "start", "a", 10),
            RoadEdge("A2", "a", "end", 10),
            RoadEdge("B1", "start", "b", 14),
            RoadEdge("B2", "b", "end", 14),
        ]
    )

    normal = graph.shortest_path("start", "end")
    incident = graph.shortest_path(
        "start",
        "end",
        edge_cost=lambda edge, _: 100
        if edge.edge_id == "A2"
        else edge.base_travel_time_s,
    )

    assert normal.edge_ids == ("A1", "A2")
    assert incident.edge_ids == ("B1", "B2")


@pytest.mark.parametrize(
    ("current", "candidate", "expected"),
    [(100, 92, False), (100, 89, True), (400, 385, False), (400, 379, True)],
)
def test_route_hysteresis(current: float, candidate: float, expected: bool) -> None:
    assert should_switch_route(current, candidate) is expected
