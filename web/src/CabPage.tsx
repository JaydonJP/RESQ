import LiveMap from "./LiveMap";
import type { Snapshot } from "./types";

export default function CabPage({ snapshot }: { snapshot: Snapshot | null }) {
  const route = snapshot?.routes.find((item) => item.selected);
  const nextSignal = snapshot?.signals[0];
  const speed = Math.round((snapshot?.vehicle.speed_mps ?? 0) * 3.6);
  const eta = route ? `${Math.floor(route.eta_s / 60).toString().padStart(2, "0")}:${Math.round(route.eta_s % 60).toString().padStart(2, "0")}` : "--:--";
  return (
    <main className="cab-page">
      <header className="page-intro cab-intro"><div><span className="overline">Driver view <span className="heading-divider" /> AMB-01</span><h1>Stay on course<span className="period">.</span></h1></div><p>{snapshot?.health.perception_online ? "Perception online" : "Camera degraded"}</p></header>
      <div className="cab-layout">
        <section className="cab-map" aria-label="Driver navigation map"><LiveMap snapshot={snapshot} followVehicle /><div className="cab-map-caption"><span>ACTIVE ROUTE</span><strong>{route?.label ?? "Calculating route"}</strong></div></section>
        <aside className="cab-instructions">
          <div className="cab-maneuver"><span className="section-label">Route guidance</span><strong>Stay on route</strong><p>{route?.label ?? "Calculating route"}</p></div>
          <div className="cab-signal"><span className="section-label">Next signal <b>{nextSignal?.intersection_id ?? "--"}</b></span><strong className={nextSignal?.phase === "pre_clear" ? "ready" : ""}>{nextSignal?.phase === "pre_clear" ? "Pre-clear" : nextSignal?.phase.replaceAll("_", " ") ?? "Awaiting signal"}</strong><p>{nextSignal?.seconds_to_change != null ? `Changes in ${nextSignal.seconds_to_change.toFixed(0)} s` : "Signal timing pending"}</p></div>
          <div className="cab-numbers"><div><span>Arrival</span><strong>{eta}</strong></div><div><span>Speed</span><strong>{speed}<small> km/h</small></strong></div></div>
          <div className="cab-footnote">Route guidance updates with the live mission.</div>
        </aside>
      </div>
    </main>
  );
}
