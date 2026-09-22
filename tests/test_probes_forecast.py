import pytest

from forecast import HistoricalAverageForecaster, SpatialTemporalForecaster, SpeedRecord
from sim.probes import ProbeAggregator, ProbeGenerator, VehicleTruth


def test_probe_generation_and_aggregation_are_seeded() -> None:
    vehicles = [
        VehicleTruth(f"car-{index}", "A1", 13.06, 80.24, 10 + index / 10)
        for index in range(100)
    ]
    generator = ProbeGenerator(adoption_percent=30, gps_noise_m=5, dropout_rate=0, seed=2)
    samples = generator.emit(vehicles)
    aggregate = ProbeAggregator(30).aggregate(samples)[0]
    assert 20 <= len(samples) <= 40
    assert aggregate.estimated_vehicle_count == pytest.approx(aggregate.sample_count / 0.3)
    assert 9 < aggregate.speed_mps < 21


def test_historical_average_uses_target_time_bucket() -> None:
    model = HistoricalAverageForecaster(bucket_minutes=15).fit(
        [
            SpeedRecord("A1", 0, 10),
            SpeedRecord("A1", 5, 12),
            SpeedRecord("A1", 20, 6),
        ]
    )
    assert model.predict("A1", 0, 5).speed_mps == 11
    assert model.predict("A1", 0, 20).speed_mps == 6


def test_spatial_forecast_returns_all_horizons() -> None:
    model = SpatialTemporalForecaster({"A1": ["A2"]})
    forecasts = model.predict({"A1": [12, 10], "A2": [8, 7]}, "A1")
    assert [item.horizon_minutes for item in forecasts] == [5, 15, 30]
    assert all(item.speed_mps > 0 for item in forecasts)
