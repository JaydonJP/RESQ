from experiments.runner import FastScenarioRunner
from schema import BaselineId, ExperimentConfig, ScenarioName


def test_seeded_run_is_repeatable() -> None:
    config = ExperimentConfig(
        baseline=BaselineId.B5,
        scenario=ScenarioName.HIDDEN_ACCIDENT,
        seed=4,
    )
    first = FastScenarioRunner().run(config)
    second = FastScenarioRunner().run(config)
    assert first.model_dump(exclude={"run_id"}) == second.model_dump(exclude={"run_id"})


def test_full_system_beats_no_system_in_hidden_accident() -> None:
    runner = FastScenarioRunner()
    b0 = runner.run(
        ExperimentConfig(baseline=BaselineId.B0, scenario=ScenarioName.HIDDEN_ACCIDENT, seed=8)
    )
    b5 = runner.run(
        ExperimentConfig(baseline=BaselineId.B5, scenario=ScenarioName.HIDDEN_ACCIDENT, seed=8)
    )
    assert b5.ambulance_travel_time_s < b0.ambulance_travel_time_s
    assert b5.route_switches == 1
    assert b5.conflicting_green_violations == 0


def test_matrix_contains_every_requested_cell() -> None:
    metrics = FastScenarioRunner().matrix(
        [BaselineId.B0, BaselineId.B5],
        [ScenarioName.OFF_PEAK, ScenarioName.SATURATED],
        seeds=3,
    )
    assert len(metrics) == 12
