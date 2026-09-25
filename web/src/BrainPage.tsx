import { useEffect, useState } from "react";
import LiveMap from "./LiveMap";
import type { Snapshot } from "./types";

function eta(seconds: number) {
  if (seconds >= 900) return "Blocked";
  return `${Math.floor(seconds / 60).toString().padStart(2, "0")}:${Math.round(seconds % 60).toString().padStart(2, "0")}`;
}

async function patchBrainControls(changes: Record<string, boolean | number>) {
  await fetch("/api/brain/controls", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
}

export default function BrainPage() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retry: number | undefined;
    let disposed = false;
    const connect = () => {
      const protocol = location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${protocol}://${location.host}/ws/brain`);
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

  const selectedRoute = snapshot?.routes.find((route) => route.selected);
  const alternateRoutes = snapshot?.routes.filter((route) => !route.selected) ?? [];
  const controls = snapshot?.controls;
  const activeModelCount =
    (controls?.historical_model_enabled ? 1 : 0) + (controls?.spatial_temporal_model_enabled ? 1 : 0);

  return (
    <main className="live-page">
      <header className="live-heading">
        <div className="live-heading-main">
          <p className="overline">
            Forecast-only decision engine <span className="heading-divider" /> No perception or macro feed wired yet
          </p>
          <h1>The brain<span className="period">.</span></h1>
          <p className="heading-subtitle">
            AMB-01 <span /> Route and signal decisions fused from {activeModelCount || "no"} forecasting{" "}
            {activeModelCount === 1 ? "model" : "models"}
          </p>
        </div>
        <div className="heading-eta">
          <span>Estimated arrival</span>
          <strong>{selectedRoute ? eta(selectedRoute.eta_s) : "--:--"}</strong>
          <small>min : sec</small>
        </div>
      </header>

      <div className="live-layout">
        <section className="map-panel" aria-label="Brain-driven route map">
          <LiveMap snapshot={snapshot} />
          <div className="map-coordinate">
            {snapshot ? `${snapshot.vehicle.position.lat.toFixed(4)}° N   ${snapshot.vehicle.position.lon.toFixed(4)}° E` : "13.0620° N   80.2445° E"}
          </div>
          <div className="map-legend">
            <span><i className="selected-line" />Brain-selected route</span>
            <span><i />Alternative</span>
          </div>
          <div className="map-caption"><span>LIVE POSITION</span><b>{snapshot?.vehicle.vehicle_id ?? "AMB-01"}</b></div>
        </section>

        <aside className="context-panel" aria-label="Brain decision context">
          <section className="context-section route-summary">
            <div className="section-label">Selected route <span className="status-mark">Active</span></div>
            <h2>{selectedRoute?.label ?? "Awaiting decision"}</h2>
            <p>{selectedRoute?.reason ?? "The brain will pick a route once forecasts arrive."}</p>
            {alternateRoutes.length > 0 && (
              <div className="route-options">
                {alternateRoutes.map((route) => (
                  <div key={route.route_id}><span>{route.label}</span><strong>{eta(route.eta_s)}</strong></div>
                ))}
              </div>
            )}
          </section>

          <section className="context-section next-signal">
            <div className="section-label">Corridor signals</div>
            {snapshot?.signals.length ? (
              <div className="corridor-line" aria-label="Upcoming intersections">
                {snapshot.signals.map((signal) => (
                  <div className={signal.phase} key={signal.intersection_id}>
                    <i /><b>{signal.intersection_id}</b>
                  </div>
                ))}
              </div>
            ) : (
              <p>Signal timing will appear here.</p>
            )}
          </section>

          <section className="context-section system-readout">
            <div className="section-label">Fusion confidence</div>
            <div>
              <strong>{Math.round((snapshot?.health.overall_confidence ?? 0) * 100)}%</strong>
              <span>{activeModelCount} of 2 models active</span>
            </div>
            <p>Perception and macro feed: not wired into the brain yet — forecasting only.</p>
          </section>

          <details className="controls-drawer" open>
            <summary>Brain controls <span>Toggle model inputs live</span></summary>
            <div className="controls-body">
              <Control
                label="Historical-average forecaster"
                checked={controls?.historical_model_enabled ?? true}
                onChange={(value) => patchBrainControls({ historical_model_enabled: value })}
              />
              <Control
                label="Spatial-temporal forecaster"
                checked={controls?.spatial_temporal_model_enabled ?? true}
                onChange={(value) => patchBrainControls({ spatial_temporal_model_enabled: value })}
              />
              <Control
                label="Inject forecast congestion scenario"
                checked={controls?.congestion_scenario ?? false}
                onChange={(value) => patchBrainControls({ congestion_scenario: value })}
                danger
              />
            </div>
          </details>
        </aside>
      </div>

      <p className="demo-disclosure">
        Brain vertical slice: forecasting output is fused and turned into a route and signal decision with no staged
        script. Turn off both forecasters to see the brain fall back to static travel times, or leave only one on to
        see it decide from a single model. Connection: {connected ? "live" : "reconnecting…"}
      </p>

      <section className="decision-log" aria-label="Decision log">
        <div><span className="section-label">Decision log</span><h2>Recent decisions.</h2></div>
        <ol>
          {snapshot?.decisions.length ? (
            snapshot.decisions.slice(-6).map((event, index) => (
              <li key={`${event.kind}-${event.at_s}-${index}`}>
                <time>{event.at_s.toFixed(1)}s</time>
                <strong>{event.message}</strong>
                <span>{event.kind.replaceAll("_", " ")}</span>
              </li>
            ))
          ) : (
            <li className="empty-log">Decisions will appear as the brain ticks.</li>
          )}
        </ol>
      </section>
    </main>
  );
}

function Control({ label, checked, onChange, danger = false }: { label: string; checked: boolean; onChange: (value: boolean) => void; danger?: boolean }) {
  return (
    <label className={`control ${danger ? "danger" : ""}`}>
      <span>{label}</span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <i />
    </label>
  );
}
