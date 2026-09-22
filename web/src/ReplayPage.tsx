import { useEffect, useState } from "react";
import ReplayMap from "./ReplayMap";
import type { GhostReplay } from "./types";

const colors = { B0: "#535f59", B5: "#269d38" } as const;
const names = { B0: "Regular ambulance", B5: "ResQ demo" } as const;

export default function ReplayPage() {
  const [replay, setReplay] = useState<GhostReplay | null>(null);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch("/api/replays/ghost?seed=7").then((response) => {
      if (!response.ok) throw new Error("Replay unavailable");
      return response.json();
    }).then(setReplay).catch(() => setError(true));
  }, []);

  useEffect(() => {
    if (!playing || !replay) return;
    const timer = window.setInterval(() => {
      setIndex((current) => current >= replay.frames.length - 1 ? 0 : current + 1);
    }, 180);
    return () => clearInterval(timer);
  }, [playing, replay]);

  const frame = replay?.frames[index];
  const baseline = replay?.metrics.find((item) => item.baseline === "B0");
  const resq = replay?.metrics.find((item) => item.baseline === "B5");
  const saved = baseline && resq ? Math.max(0, baseline.ambulance_travel_time_s - resq.ambulance_travel_time_s) : 0;

  if (error) return <main className="state-page"><h1>Replay unavailable.</h1><p>Check the simulation connection and reload the page.</p></main>;
  if (!replay || !frame) return <main className="state-page"><h1>Preparing replay.</h1><p>Loading the recorded route and vehicle positions.</p></main>;

  return (
    <main className="replay-page">
      <header className="page-intro replay-intro"><div><span className="overline">Review demonstration <span className="heading-divider" /> Road-network scenario</span><h1>Same emergency. Different route<span className="period">.</span></h1><p>Two ambulances start together on mapped Chennai roads. A staged incident delays the regular route; ResQ is shown taking a connected bypass.</p></div><div className="replay-clock">{frame.t_s.toFixed(0)} <span>/ {replay.duration_s.toFixed(0)} s</span></div></header>
      <div className="replay-layout">
        <section className="replay-stage">
          <div className="stage-topline"><span>DRIVABLE OSM ROAD GEOMETRY</span><span>NUNGAMBAKKAM → APOLLO HOSPITALS</span></div>
          <ReplayMap replay={replay} frameIndex={index} />
          <div className="replay-map-legend"><span><i className="regular-line" /> Regular ambulance</span><span><i className="resq-line" /> ResQ bypass</span><span><i className="incident-dot" /> Staged incident</span></div>
          <div className="replay-controls"><button onClick={() => setPlaying(!playing)}>{playing ? "Pause" : "Play"} <span aria-hidden="true">{playing ? "Ⅱ" : "▶"}</span></button><input aria-label="Replay position" type="range" min="0" max={replay.frames.length - 1} value={index} onChange={(event) => { setPlaying(false); setIndex(Number(event.target.value)); }} /><time>{frame.t_s.toFixed(0)}s</time></div>
          <div className="replay-event"><span>AT THIS MOMENT</span><strong>{frame.event ?? (frame.vehicles[0]?.progress === frame.vehicles[1]?.progress ? "Both ambulances are advancing on mapped roads." : "Vehicles advance on their separate mapped routes.")}</strong></div>
        </section>
        <aside className="replay-aside">
          <div className="replay-result"><span className="section-label">Assumed time advantage</span><strong>{saved.toFixed(0)}<small> seconds</small></strong><p>Illustrative only. This is not a measured model or SUMO result.</p></div>
          <section className="finish-list"><h2>Scenario timing</h2>{[...replay.metrics].sort((a,b) => a.ambulance_travel_time_s-b.ambulance_travel_time_s).map((metric, rank) => <div className="finish" key={metric.baseline}><span>{String(rank + 1).padStart(2, "0")}</span><i style={{ background: colors[metric.baseline as keyof typeof colors] ?? "#89847a" }} /><b>{names[metric.baseline as keyof typeof names] ?? metric.baseline}</b><strong>{metric.ambulance_travel_time_s.toFixed(0)}s</strong></div>)}</section>
          <section className="demo-assumptions"><h2>What this demo assumes</h2><ul>{replay.assumptions.map((item) => <li key={item}>{item}</li>)}</ul></section>
        </aside>
      </div>
    </main>
  );
}
