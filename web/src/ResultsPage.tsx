import { useEffect, useMemo, useState } from "react";
import type { ResultsSummary } from "./types";

export default function ResultsPage() {
  const [results, setResults] = useState<ResultsSummary | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(false);
  const load = () => fetch("/api/results").then((response) => {
    if (!response.ok) throw new Error("Results unavailable");
    return response.json();
  }).then(setResults).catch(() => setError(true));
  useEffect(() => { load(); }, []);
  const runMatrix = async () => {
    setRunning(true);
    setError(false);
    try {
      const response = await fetch("/api/experiments/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ seeds: 5 }) });
      if (!response.ok) throw new Error("Experiment failed");
      setResults(await response.json());
    } catch { setError(true); }
    finally { setRunning(false); }
  };
  const maxTime = Math.max(...(results?.baselines.map((item) => item.p95_travel_time_s) ?? [1]));
  const improvement = useMemo(() => {
    const b0 = results?.baselines.find((item) => item.baseline === "B0")?.mean_travel_time_s;
    const b5 = results?.baselines.find((item) => item.baseline === "B5")?.mean_travel_time_s;
    return b0 && b5 ? (1 - b5 / b0) * 100 : 0;
  }, [results]);
  const resq = results?.baselines.find((item) => item.baseline === "B5");
  if (!results) return <main className="state-page"><h1>{error ? "Results unavailable." : "Reading the evidence."}</h1><p>{error ? "Check the experiment service and reload the page." : "Aggregating recorded experiment runs."}</p></main>;
  return (
    <main className="results-page">
      <header className="page-intro results-intro"><div><span className="overline">Synthetic fast-mode estimates <span className="heading-divider" /> B0–B5 comparison</span><h1>Scenario estimates, not field results<span className="period">.</span></h1><p>{results.total_runs} deterministic formula-based runs across {results.scenarios.length} scenarios. These are not SUMO outputs or measured ambulance performance.</p></div><button className="action-button" onClick={runMatrix} disabled={running}>{running ? "Running estimates…" : "Generate 5 more seeds"}</button></header>
      {error && <p className="inline-error" role="alert">The new experiment did not complete. Existing results are still shown.</p>}
      <section className="result-hero"><div><span className="section-label">Illustrative model estimate</span><h2>{improvement.toFixed(1)}<span>%</span> faster<br />in the formula.</h2><p>Mean generated travel time for B5 compared with B0. This is a hypothesis to test in a traffic simulator.</p></div><div className="result-support"><div><span>Assumed green on arrival</span><strong>{resq ? (resq.mean_green_on_arrival_rate * 100).toFixed(1) : "—"}%</strong><small>B5 synthetic mean</small></div><div><span>Scenarios</span><strong>{results.scenarios.length}</strong><small>from off-peak to degraded camera</small></div></div></section>
      <section className="chart-section"><div className="chart-intro"><div><span className="section-label">Ambulance travel time</span><h2>How each system compares.</h2></div><p>Mean trip time, with p95 marker. Seconds; lower is better. Values at right show mean ± 95% CI.</p></div><div className="bar-chart"><div className="axis-labels"><span>0 s</span><span>{Math.round(maxTime / 2)} s</span><span>{Math.round(maxTime)} s</span></div>{results.baselines.map((item) => <div className={`bar-row ${item.baseline === "B5" ? "resq-row" : ""}`} key={item.baseline}><div className="bar-name"><b>{item.baseline}</b><small>{item.baseline === "B5" ? "ResQ" : item.baseline === "B0" ? "Baseline" : "Comparison"}</small></div><div className="bar-plot"><i style={{ width: `${item.mean_travel_time_s / maxTime * 100}%` }} /><span style={{ left: `${item.p95_travel_time_s / maxTime * 100}%` }} title={`p95 ${item.p95_travel_time_s.toFixed(1)} seconds`} /></div><strong>{item.mean_travel_time_s.toFixed(1)} <small>± {item.ci95_travel_time_s.toFixed(1)} s</small></strong></div>)}</div></section>
      <section className="results-table"><div className="chart-intro"><div><span className="section-label">Full comparison</span><h2>System and cross-traffic.</h2></div><p>Each row represents one baseline across the same scenario set.</p></div><div className="table-scroll"><table><thead><tr><th>Baseline</th><th>Runs</th><th>Green on arrival</th><th>Mean stops</th><th>Cross-traffic delay</th><th>p95 trip</th></tr></thead><tbody>{results.baselines.map((item) => <tr key={item.baseline}><td><b>{item.baseline}</b></td><td>{item.runs}</td><td>{(item.mean_green_on_arrival_rate * 100).toFixed(1)}%</td><td>{item.mean_stops.toFixed(2)}</td><td>{item.mean_cross_traffic_delay_s.toFixed(1)}s</td><td>{item.p95_travel_time_s.toFixed(1)}s</td></tr>)}</tbody></table></div></section>
    </main>
  );
}
