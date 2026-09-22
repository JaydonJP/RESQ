"""SQLite-backed run index and replay store."""

from __future__ import annotations

import json
import math
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean, stdev

from schema import (
    BaselineId,
    BaselineSummary,
    ResultsSummary,
    RunMetrics,
)

DEFAULT_DB = Path(__file__).resolve().parents[1] / "runs" / "resq_green.sqlite3"


class RunStore:
    def __init__(self, path: str | Path | None = None) -> None:
        configured = path or os.getenv("RESQ_GREEN_DB") or DEFAULT_DB
        self.path = Path(configured)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialise(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    baseline TEXT NOT NULL,
                    scenario TEXT NOT NULL,
                    seed INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    metrics_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS runs_matrix ON runs (baseline, scenario, seed)"
            )

    def save_many(self, metrics: list[RunMetrics]) -> int:
        rows = [
            (
                item.run_id,
                item.baseline.value,
                item.scenario.value,
                item.seed,
                datetime.now(UTC).isoformat(),
                item.model_dump_json(),
            )
            for item in metrics
        ]
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT OR REPLACE INTO runs
                (run_id, baseline, scenario, seed, created_at, metrics_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0])

    def list_metrics(self, limit: int | None = None) -> list[RunMetrics]:
        query = "SELECT metrics_json FROM runs ORDER BY created_at DESC"
        parameters: tuple[int, ...] = ()
        if limit is not None:
            query += " LIMIT ?"
            parameters = (limit,)
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [RunMetrics.model_validate(json.loads(row[0])) for row in rows]

    def summary(self) -> ResultsSummary:
        metrics = self.list_metrics()
        summaries: list[BaselineSummary] = []
        for baseline in BaselineId:
            items = [item for item in metrics if item.baseline == baseline]
            values = sorted(item.ambulance_travel_time_s for item in items)
            if not items:
                summaries.append(
                    BaselineSummary(
                        baseline=baseline,
                        runs=0,
                        mean_travel_time_s=0,
                        ci95_travel_time_s=0,
                        p95_travel_time_s=0,
                        mean_green_on_arrival_rate=0,
                        mean_cross_traffic_delay_s=0,
                        mean_stops=0,
                    )
                )
                continue
            ci95 = 0.0 if len(values) < 2 else 1.96 * stdev(values) / math.sqrt(len(values))
            p95_index = min(len(values) - 1, math.ceil(0.95 * len(values)) - 1)
            summaries.append(
                BaselineSummary(
                    baseline=baseline,
                    runs=len(items),
                    mean_travel_time_s=round(fmean(values), 3),
                    ci95_travel_time_s=round(ci95, 3),
                    p95_travel_time_s=round(values[p95_index], 3),
                    mean_green_on_arrival_rate=round(
                        fmean(item.green_on_arrival_rate for item in items), 4
                    ),
                    mean_cross_traffic_delay_s=round(
                        fmean(item.cross_traffic_added_delay_s for item in items), 3
                    ),
                    mean_stops=round(fmean(item.stops for item in items), 3),
                )
            )
        scenarios = sorted({item.scenario for item in metrics}, key=lambda item: item.value)
        return ResultsSummary(
            total_runs=len(metrics),
            scenarios=scenarios,
            baselines=summaries,
        )
