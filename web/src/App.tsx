import { useEffect, useMemo, useState } from "react";
import CabPage from "./CabPage";
import LiveMap from "./LiveMap";
import ReplayPage from "./ReplayPage";
import ResultsPage from "./ResultsPage";
import type { Snapshot } from "./types";

type Page = "Live" | "Replay" | "Cab" | "Results";

function eta(seconds: number) {
  if (seconds >= 900) return "Blocked";
  return `${Math.floor(seconds / 60).toString().padStart(2, "0")}:${Math.round(seconds % 60).toString().padStart(2, "0")}`;
}

async function patchControls(changes: Record<string, boolean | number>) {
  await fetch("/api/controls", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
}

export default function App() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const [page, setPage] = useState<Page>("Live");

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retry: number | undefined;
    let disposed = false;
    const connect = () => {
      const protocol = location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${protocol}://${location.host}/ws/live`);
      socket.onopen = () => setConnected(true);
      socket.onmessage = (event) => setSnapshot(JSON.parse(event.data) as Snapshot);
      socket.onclose = () => {
        setConnected(false);
        if (!disposed) retry = window.setTimeout(connect, 1200);
      };
    };
    connect();
    return () => {
      disposed = true;
      if (retry) clearTimeout(retry);
      socket?.close();
    };
  }, []);

  const selectedRoute = useMemo(() => snapshot?.routes.find((route) => route.selected), [snapshot]);
  const alternateRoutes = snapshot?.routes.filter((route) => !route.selected) ?? [];
  const nextSignal = snapshot?.signals[0];
  const blockedRoads = snapshot?.roads.filter((road) => road.blockage) ?? [];

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand" aria-label="ResQ">Res<span>Q</span><i /></div>
        <nav aria-label="Main navigation">
          {(["Live", "Replay", "Cab", "Results"] as Page[]).map((item) => (
            <button type="button" className={page === item ? "active" : ""} aria-current={page === item ? "page" : undefined} onClick={() => setPage(item)} key={item}>{item}</button>
          ))}
        </nav>
        <div className={`connection ${connected ? "online" : ""}`} role="status"><i />{connected ? "System online" : "Connecting"}</div>
      </header>

      {page === "Live" && (
        <main className="live-page">
          <header className="live-heading">
            <div className="live-heading-main">
              <p className="overline">Interactive road-network demo <span className="heading-divider" /> Chennai, India</p>
              <h1>Clear the path<span className="period">.</span></h1>
              <p className="heading-subtitle">AMB-01 <span /> Apollo Hospitals, Greams Road</p>
            </div>
            <div className="heading-eta"><span>Estimated arrival</span><strong>{selectedRoute ? eta(selectedRoute.eta_s) : "--:--"}</strong><small>min : sec</small></div>
          </header>

          <div className="live-layout">
            <section className="map-panel" aria-label="Live route map">
              <LiveMap snapshot={snapshot} />
              <div className="map-coordinate">{snapshot ? `${snapshot.vehicle.position.lat.toFixed(4)}° N   ${snapshot.vehicle.position.lon.toFixed(4)}° E` : "13.0620° N   80.2445° E"}</div>
              <div className="map-legend"><span><i className="selected-line" />Active route</span><span><i />Alternative</span><span><i className="blocked-line" />Staged incident</span></div>
              <div className="map-caption"><span>LIVE POSITION</span><b>{snapshot?.vehicle.vehicle_id ?? "AMB-01"}</b></div>
            </section>

            <aside className="context-panel" aria-label="Mission context">
              <section className="context-section route-summary">
                <div className="section-label">Current route <span className="status-mark">Active</span></div>
                <h2>{selectedRoute?.label ?? "Awaiting route"}</h2>
                <p>{selectedRoute?.reason ?? "Route selection will appear when the simulation connects."}</p>
                {alternateRoutes.length > 0 && <div className="route-options">{alternateRoutes.map((route) => <div key={route.route_id}><span>{route.label}</span><strong>{eta(route.eta_s)}</strong></div>)}</div>}
              </section>

              <section className="context-section next-signal">
                <div className="section-label">Next intersection</div>
                <div className="signal-feature"><strong>{nextSignal?.intersection_id ?? "--"}</strong><span className={`phase ${nextSignal?.phase ?? ""}`}>{nextSignal?.phase.replaceAll("_", " ") ?? "Awaiting signal"}</span></div>
                <p>{nextSignal?.seconds_to_change != null ? `Signal changes in ${nextSignal.seconds_to_change.toFixed(0)} s` : "Signal timing will appear here."}</p>
                {snapshot?.signals && snapshot.signals.length > 1 && <div className="corridor-line" aria-label="Upcoming intersections">{snapshot.signals.map((signal) => <div className={signal.phase} key={signal.intersection_id}><i /><b>{signal.intersection_id}</b></div>)}</div>}
              </section>

              {blockedRoads.length > 0 && <section className="incident-note" role="alert"><span>Incident detected</span><strong>{blockedRoads.length} blocked {blockedRoads.length === 1 ? "road" : "roads"}</strong><p>{blockedRoads[0].explanation}</p></section>}

              <section className="context-section system-readout">
                <div className="section-label">System confidence</div>
                <div><strong>{Math.round((snapshot?.health.overall_confidence ?? 0) * 100)}%</strong><span>{snapshot?.health.perception_online ? "Camera active" : "Camera degraded"}</span></div>
                <p>Macro feed {snapshot?.controls.macro_feed ? "active" : "inactive"} <span>·</span> Probe adoption {snapshot?.controls.adoption_percent ?? 10}%</p>
              </section>

              <details className="controls-drawer"><summary>Simulation controls <span>Adjust scenario</span></summary><div className="controls-body">
                <Control label="Inject staged incident (restarts demo)" checked={snapshot?.controls.accident ?? false} onChange={(value) => patchControls({ accident: value })} danger />
                <Control label="Macro traffic feed" checked={snapshot?.controls.macro_feed ?? false} onChange={(value) => patchControls({ macro_feed: value })} />
                <Control label="Ambulance camera" checked={snapshot?.controls.camera ?? false} onChange={(value) => patchControls({ camera: value })} />
                <label className="range"><span>Probe adoption <b>{snapshot?.controls.adoption_percent ?? 10}%</b></span><input type="range" min="5" max="30" step="5" value={snapshot?.controls.adoption_percent ?? 10} onChange={(event) => patchControls({ adoption_percent: Number(event.target.value) })} /></label>
              </div></details>
            </aside>
          </div>

          <p className="demo-disclosure">Demonstration mode: road routes are computed on local OpenStreetMap geometry. Traffic, incident timing, signal states, and sensor detections are staged—not live telemetry or validated model predictions.</p>
          <section className="decision-log" aria-label="Decision log"><div><span className="section-label">Decision log</span><h2>Recent decisions.</h2></div><ol>{snapshot?.decisions.length ? snapshot.decisions.slice(-4).map((event, index) => <li key={`${event.kind}-${event.at_s}-${index}`}><time>{event.at_s.toFixed(1)}s</time><strong>{event.message}</strong><span>{event.kind.replaceAll("_", " ")}</span></li>) : <li className="empty-log">Decisions will appear as the mission progresses.</li>}</ol></section>
        </main>
      )}
      {page === "Replay" && <ReplayPage />}
      {page === "Cab" && <CabPage snapshot={snapshot} />}
      {page === "Results" && <ResultsPage />}
    </div>
  );
}

function Control({ label, checked, onChange, danger = false }: { label: string; checked: boolean; onChange: (value: boolean) => void; danger?: boolean }) {
  return <label className={`control ${danger ? "danger" : ""}`}><span>{label}</span><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /><i /></label>;
}
