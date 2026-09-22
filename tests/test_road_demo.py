from recorder.replay import build_ghost_replay
from sim.chennai.roads import RoadNetwork, demo_plan, distance_m, point_along
from sim.demo import INCIDENT_QUEUE_S, DemoSimulation


def test_routes_use_connected_drivable_osm_edges() -> None:
    network = RoadNetwork()
    plan = demo_plan()
    assert distance_m(plan.origin, plan.normal.geometry[0]) < 1
    assert distance_m(plan.hospital, plan.normal.geometry[-1]) < 1
    for path in (plan.normal, plan.bypass):
        assert len(path.geometry) == len(path.edges) + 1
        assert len(path.edges) > 30
        for start, finish, edge_id in zip(path.nodes, path.nodes[1:], path.edges, strict=False):
            assert any(
                edge.target == finish and edge.edge_id == edge_id
                for edge in network.adjacency[start]
            )
        for fraction in (0, 0.13, 0.42, 0.79, 1):
            point = point_along(path, fraction)
            assert network.nodes
            assert (
                min(
                    distance_m(point, a) + distance_m(point, b) - distance_m(a, b)
                    for a, b in zip(path.geometry, path.geometry[1:], strict=False)
                )
                < 0.05
            )
    assert not set(plan.bypass.edges) & plan.blocked_edges


def test_staged_replay_waits_and_has_explicit_assumptions() -> None:
    replay = build_ghost_replay()
    normal = demo_plan().normal
    regular = replay.metrics[0]
    resq = replay.metrics[1]
    assert regular.ambulance_travel_time_s == normal.travel_s + INCIDENT_QUEUE_S
    assert resq.ambulance_travel_time_s < regular.ambulance_travel_time_s
    assert replay.demonstration_only and len(replay.assumptions) >= 3
    stationary = [frame for frame in replay.frames if frame.vehicles[0].position == replay.incident]
    assert len(stationary) >= 50  # two-second frames during the 120-second queue


def test_live_demo_keeps_working_with_feeds_disabled() -> None:
    simulation = DemoSimulation()
    simulation.update_controls(macro_feed=False, camera=False, accident=True)
    snapshot = simulation.snapshot()
    assert snapshot.vehicle.route_id == "route-a"
    assert len(snapshot.routes[0].geometry) > 30
    simulation.update_controls(camera=True)
    assert simulation.snapshot().vehicle.route_id == "route-b"
