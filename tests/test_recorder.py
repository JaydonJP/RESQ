from experiments.runner import FastScenarioRunner
from recorder import RunStore
from schema import BaselineId, ScenarioName


def test_store_summarises_saved_runs(tmp_path) -> None:
    store = RunStore(tmp_path / "runs.sqlite3")
    metrics = FastScenarioRunner().matrix(
        [BaselineId.B0, BaselineId.B5], [ScenarioName.HIDDEN_ACCIDENT], seeds=4
    )
    assert store.save_many(metrics) == 8
    summary = store.summary()
    assert summary.total_runs == 8
    b5 = next(item for item in summary.baselines if item.baseline == BaselineId.B5)
    assert b5.runs == 4
    assert b5.ci95_travel_time_s > 0
