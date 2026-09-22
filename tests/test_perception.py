from perception import BlockageDetector, TrackedObject, cluster_lidar, predict_tracks


def test_multi_lane_stopped_queue_is_a_blockage() -> None:
    tracks = [
        TrackedObject(str(index), "car", f"lane-{index % 2}", 20 + index, 0, 0, 5, 0.92)
        for index in range(4)
    ]
    observation = BlockageDetector().observe("A2", tracks)
    assert observation.blockage is True
    assert observation.confidence > 0.9


def test_constant_velocity_prediction_and_lidar_clusters() -> None:
    track = TrackedObject("one", "car", "lane-1", 20, 2, 5, 0, 0.9)
    prediction = predict_tracks([track], horizon_s=2)[0]
    assert prediction.distance_m == 10
    assert prediction.gap_opening is True
    points = [(0, 0, 1), (0.2, 0.1, 1), (0.3, 0, 1), (8, 8, 1), (8.1, 8, 1), (8, 8.2, 1)]
    assert len(cluster_lidar(points, radius_m=0.5)) == 2
