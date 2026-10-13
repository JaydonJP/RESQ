# ResQ: from research prototype to a system hospitals can use

**Implementation plan, version 1.1.** Written 11 October 2026; reviewed 13 October 2026. Covers 12 October 2026 to 16 May 2027 (31 weeks, 3 people).

### Review decisions (13 October 2026)

- **Prove one end-to-end hospital workflow before expanding the stack.** The first vertical slice is
  one mission, one simulated/drive-test vehicle, a desk assignment, a crew status update, a
  deliberately non-clinical arrival notice, an ED acknowledgement, and an auditable handover.
  Defer destination ranking, FHIR, forecast fine-tuning and signal control until this works.
- **Split the pilot into two data gates.** Stage A uses staff-authorised vehicle telemetry,
  mission timing and synthetic pre-alerts. Stage B may use real encounter attributes only after
  the hospital has agreed on access, retention and the ethics review path. Omitting names does not
  establish anonymity: location, timestamps and clinical details can identify people together.
- **Make safety claims measurable.** A controller without SUMO/controller phase observations reports
  conflicting greens as *unknown*. A zero count is reportable only for a run that monitored every
  controlled junction and has a complete observation record.
- **Treat the manual corridor as an officer workflow.** ResQ may show a predicted approach and
  request acknowledgement; only authorised police decide when to hold or release traffic. On stale
  GPS or a missed pass, the screen marks the prediction stale and escalates to the nodal officer.
- **Use evidence gates for optional infrastructure.** PostGIS and a durable audit store are needed
  for the pilot. Add TimescaleDB, Arq, MLflow and the larger observability stack only when measured
  load or a demonstrated workflow requires them. A Valhalla live-speed write remains a spike.

These decisions revise the affected sections below. External dates, prices, product capabilities
and legal interpretations must be reconfirmed before procurement or a live pilot.

This plan replaces nothing that already works. It builds on the existing repository and changes
what the project is *for*. ResQ stops being "a simulation that proves predictive routing helps an
ambulance" and becomes **"software a hospital's ambulance desk, emergency department, and the
traffic police can use on a real mission"**. The simulation becomes the test bench that proves the
software is safe before anyone relies on it.

---

## 0. The recommendation on one page

1. **Change the customer.** Today the user is an examiner watching a demo. The new users are
   **(a)** the ambulance crew, **(b)** the receiving emergency department (ED), **(c)** the
   hospital's ambulance coordinator, and **(d)** the traffic-police nodal officer and the
   constables at junctions.
2. **Build the part hospitals can use without anyone's permission first.** A hospital controls
   its ambulances and its ED. It does not control traffic signals. The first useful product
   therefore has three parts:
   - live ambulance tracking,
   - an ETA the hospital can trust, with an honest range such as "arrives in 8 to 11 minutes",
   - a structured **pre-arrival alert**, so the ED is ready before the patient reaches the door.

   The clinical evidence supports this. Pre-hospital notification combined with an ECG is
   associated with door-to-balloon times about 26 minutes shorter for heart attacks (STEMI), and
   pre-activating the catheterisation lab with a median 12 minutes saved. These are observational
   studies (see §2.4).
3. **Digitise the green corridor Chennai already runs, then automate it.** Chennai's green
   corridors are set up today by a phone call to the Deputy Commissioner of Police (Traffic). That
   officer then positions constables along the route. ResQ's first corridor product replaces the
   phone tree: it sends a request with the route, gives each junction a live countdown, and clears
   each junction's predicted approach and pass for the officer to confirm. Direct signal pre-emption through
   the city's adaptive-signal (ITMS/ATCS) system comes second and needs a formal agreement (MoU)
   with the police. Until then it is built, validated and demonstrated in SUMO.
4. **Replace hand-rolled infrastructure with proven open-source components.** Use:
   - **Valhalla** for city-scale routing, traffic-aware ETAs, isochrones, and matching GPS traces
     to roads,
   - **PostgreSQL + PostGIS** for missions and location history; add TimescaleDB if volume warrants it,
   - **Keycloak** for hospital, crew and police logins,
   - **Expo (React Native)** for the crew app.

   Keep the team's strengths: FastAPI and Pydantic, React with MapLibre, PyTorch, and SUMO.
5. **Train on real data, not only simulated data.** Every pilot trip produces a GPS trace. Match
   it to the road network and it becomes real Chennai probe data, which nobody else publishes. Use
   it for two models:
   - an ETA model: Valhalla's ETA plus a learned correction with prediction intervals,
   - a re-trained version of the existing Graph WaveNet, pre-trained on CHENNAI-SIM and then
     fine-tuned on these traces.
6. **Pilot in staged shadow mode.** The system runs alongside normal operations at one partner
   hospital for 2 to 4 weeks. Stage A measures tracking and ETA with authorised staff/vehicle
   telemetry and synthetic clinical alerts. Real pre-alerts and related lead-time measurements
   begin only after the partner approves Stage B's data and ethics pathway. Staff location and
   potentially linkable encounter data still need privacy controls.

The single most important action in the next two weeks is **finding the pilot hospital and
interviewing its people** (§14, §19). Everything else depends on what they say.

---

## 1. Where the project stands (honest audit)

### 1.1 What is real and working

| Area | State | Evidence in repo |
|---|---|---|
| Shared contracts | Pydantic v1.0 schema for observations, routes, signals, snapshots, experiments | `schema/models.py` |
| Road graph | Directed OSM extract of Thousand Lights/Nungambakkam; one-ways respected | `sim/chennai/roads.json`, `sim/chennai/roads.py` |
| SUMO scenario | Network build, background traffic, a TraCI-inserted `AMB-01`; 2.44 km in 197.6 s smoke run | `sim/chennai/build_network.py`, `sim/chennai/run_sumo.py` |
| Forecasting | Graph WaveNet trained and benchmarked: METR-LA 15-min MAE 2.76 mph (paper reports 2.69), PEMS-BAY 1.35 (paper 1.30), CHENNAI-SIM about 27 % better than both baselines; split-conformal intervals with about 89–91 % coverage | `forecast/`, `docs/TRAFFIC_FORECASTING_RUN.md` |
| Forecast → decision | Segment forecasts priced onto OSM edges, then turned into a macro observation, fused, and fed to routing | `sim/chennai/pricing.py`, `forecast/adapter.py`, `fusion/engine.py` |
| Fusion | Inverse-variance fusion with a blockage override | `fusion/engine.py` |
| Safety controller | Deterministic pre-emption state machine with minimum green, amber, all-red and recovery | `corridor/state_machine.py` |
| Web app | React 19, MapLibre, Live / Forecast / Replay / Cab / Results pages | `web/src/` |
| Engineering | 39 tests passing after this review, ruff, CI, Dockerfile, compose | `tests/`, `.github/workflows/ci.yml` |

### 1.2 What is staged or simulated (must not be presented as real)

- The **incident cue and signal states** in the Live demo are scripted (`sim/demo.py`:
  `INCIDENT_QUEUE_S = 120`, `RESQ_CUE_S = 8`).
- The **B0–B5 results** (about 28.9 % improvement, 95.8 % green-on-arrival) come from
  formula-based runs (`experiments/runner.py`), not from SUMO. The README already says this.
- **SUMO is not in the decision loop.** The ambulance in SUMO does not request green lights, and
  the dashboard is not driven by SUMO.
- **CARLA perception and YOLO** exist as interfaces only (`adapters/carla_sensors.py`,
  `perception/pipeline.py` consumes already-tracked objects).
- **Every number behind the forecast is a statement about the simulator.** No Chennai road speed
  has been measured.

### 1.3 Technical debt and defects found during this review

| # | Issue | Where | Why it matters for real use | Fix |
|---|---|---|---|---|
| D1 | Request expiry compared `datetime.now(UTC)` (wall clock) while transitions use `now_s` (simulation time) | `corridor/state_machine.py` | Replays and SUMO runs faster than real time become non-deterministic, and requests can expire at the wrong moment | **Fixed:** caller supplies `now_at` paired with `now_s`; tests use a deterministic clock |
| D2 | `conflicting_green=False` was hard-coded | `corridor/state_machine.py`, `sim/demo.py`, `experiments/runner.py` | The safety metric "zero conflicting greens" was asserted, not measured | **Started:** unobserved values are now `null`; Phase 3 must measure actual SUMO phases and coverage per junction before claiming zero |
| D3 | One global `DemoSimulation`, one global `RunStore`, no auth, fixed CORS list | `api/main.py:46-49` | A real system is multi-user, multi-mission and multi-hospital | Domain services, a DB, OIDC auth (Phase 1) |
| D4 | SQLite run store | `recorder/store.py` | Fine for experiments; not for concurrent operational data | PostgreSQL + Timescale (Phase 1) |
| D5 | Custom Dijkstra without turn restrictions, without time-of-day profiles, and limited to the 2.5 × 2 km box | `routing/engine.py` | Wrong or illegal routes at city scale | Valhalla; keep `routing/` as a research and oracle implementation |
| D6 | TS types hand-maintained in `web/src/types.ts` | `web/src/types.ts` | The client and server drift apart silently | Generate types from OpenAPI |
| D7 | Uncommitted forecast changes; three `.pptx` files, a PDF, and `trips.trips.xml` in the repo root | `git status` | Repo bloat, and the last results are not reproducible from `HEAD` | Commit the code; move decks to a `deliverables/` folder tracked with Git LFS, or out of the repo |
| D8 | Mixed naming: "ResQ" / "RESQ-Green" / "ResQ-Green" | README, decks | Confuses reviewers and future partners | Pick **ResQ** everywhere |
| D9 | Live page and WebSocket rebuild the snapshot per connection every 200 ms | `api/main.py:238-245` | Cost grows with the number of viewers | Publish once, fan out (Redis pub/sub) |

---

## 2. The real-world reality check

### 2.1 How an ambulance reaches a Chennai hospital today

- **State 108 service** (EMRI Green Health Services with the Tamil Nadu government):
  - About 1,048 life-support ambulances statewide as of May 2025, per a 2026 CAG audit.
  - A reported Chennai average response time of about 7.5 minutes, against 13.2 minutes statewide.
  - A real-time tracking app with SMS ETA links has been in testing.
- **Private hospital fleets** (Apollo, Kauvery, MGM, SIMS, Gleneagles and others) run their own
  ambulance numbers and desks. They handle both emergencies and inter-facility transfers.
- **Hospital pre-notification** is usually an ad-hoc phone call from the crew, if it happens at
  all. The ED often learns the patient's condition at the door.
- **Green corridors** are set up manually:
  - It began with the 2014 heart transport: 26 police personnel along the route cut a journey of
    more than 40 minutes to about 14.
  - Since then, a corridor is a phone call to the DCP (Traffic). That officer is the nodal officer.
  - The police move the convoy non-stop rather than closing roads.
  - The 2024 national organ-transport SOP asks every city to appoint police nodal officers and
    proposes a "one trigger" activation.

### 2.2 Signal infrastructure

- **Chennai:** The Greater Chennai Traffic Police (GCTP) planned AI adaptive signals at 165
  junctions. Data would flow to police headquarters, with manual override for ambulances and VIP
  convoys. This plan has not been confirmed as complete. **Ask GCTP directly in the interviews.**
- **Bengaluru (B-ATCS):** The system runs at about 169 junctions. Its Emergency Vehicle Priority
  feature uses GPS and BTP-approved transponders, and switches a signal when the vehicle is about
  100–200 m away. This is the nearest Indian precedent and a strong argument in an MoU discussion.
- **Elsewhere in India:** Belagavi activates green corridors from its Integrated Command and
  Control Centre (ICCC), and Delhi's ITMS is described as giving automatic green to ambulances.
- **Internationally**, cloud-to-cloud pre-emption already exists without roadside hardware, for
  example Miovision Signal Assist and Iteris VantagePriority. The standards are:
  - **NTCIP 1211** (signal control and prioritisation) at the controller,
  - **SAE J2735** Signal Request and Signal Status messages,
  - **SAE J2945/B** (2025) over the air.

**Consequence:** a hospital product cannot assume it controls signals. It must:

1. be useful with **zero** signal integration,
2. offer a **human-in-the-loop** corridor workflow for the police,
3. expose a **standards-shaped request interface** (SRM/SSM-like) so integration with an
   ATCS/ICCC is an adapter, not a rewrite.

### 2.3 Who uses ResQ and what they need

| User | Where | Job to be done | What would make them stop using it |
|---|---|---|---|
| Driver | Ambulance cab | Know the fastest route and keep driving | Anything that needs touching while moving; English-only voice; app killed by the phone's battery saver |
| Paramedic / EMT | Ambulance rear | Tell the hospital what is coming, in under 60 s, with gloves on | Long forms; no network in an underpass |
| ED charge nurse / ED doctor | ED, wall display | Know who arrives when, and how sick they are, early enough to prepare | Alert fatigue, ETAs that are wrong, more logins |
| Ambulance coordinator | Hospital desk | See every vehicle, assign missions, pick the destination | Double data entry alongside the existing register |
| Traffic nodal officer | Police control room | Approve a corridor and see where the ambulance is | Requests they did not authorise; unclear accountability |
| Junction constable | At the junction | Know when to stop cross traffic and from which direction | Needing to install an app; too-early alerts that make them hold traffic for nothing |
| Hospital management | Office | Response-time and handover statistics, at least proving value | No exportable numbers |

### 2.4 Why the hospital cares (value hypothesis)

- **Clinical readiness:** pre-alerts let the ED activate the stroke team or the cath lab before
  arrival. The bundled evidence:
  - A meta-analysis of 10 studies and 2,947 patients found door-to-balloon time 26 minutes shorter
    with a pre-hospital ECG plus hospital notification.
  - An analysis of 27,840 patients in the ACTION Registry found cath-lab pre-activation associated
    with a median 12 minutes shorter door-to-device time.
  - A stroke programme reported door-to-needle time falling from 49 to 45 minutes as
    pre-notification rose.
  - All of this is observational, and ResQ's contribution to it should be measured, not assumed.
- **Operational:** handover ("offload") times, fleet utilisation, and response-time reporting for
  accreditation (NABH asks for emergency-service indicators).
- **Reputation and partnerships:** organ transport and police coordination.

### 2.5 Chennai-specific hazards the product must handle

- **North-east monsoon (October–December):** subways and low roads flood and close. Closures need
  manual entry and expiry, and rain needs to be a model feature.
- **Metro Phase-2 construction:** diversions change monthly. OSM lags behind, so the map needs
  override patches.
- **Mixed traffic and lane-less driving**, plus flyovers (Gemini) where GPS points snap to the
  wrong level.
- **Android phones from Xiaomi, Oppo, Vivo and Realme kill background apps aggressively.** Location
  tracking must survive this, or it fails silently.

---

## 3. Product definition

### 3.1 Vision

> *Every minute between the call and the right treatment is visible, predictable, and shortened,
> without ever making the road less safe.*

### 3.2 Product surfaces

| Surface | Platform | Primary user | MVP scope |
|---|---|---|---|
| **ResQ Crew** | Android first (Expo / React Native), runs on a mounted phone | Driver + EMT | Mission inbox, route and voice guidance (Tamil/English), background GPS, status buttons, 4-tap pre-alert, corridor request |
| **ResQ ED Board** | Web, also a full-screen wall-TV mode | ED staff | Inbound list sorted by ETA, ETA range, pre-alert card, acknowledge button, audible alert, map |
| **ResQ Desk** | Web | Ambulance coordinator | Fleet map, create and assign missions, destination recommendation, closures, history and reports |
| **ResQ Corridor** | Web (control room) + a **no-install junction link** (PWA opened from WhatsApp/SMS) | Nodal officer, constables | Approve/deny, live route, per-junction countdown and approach direction, officer-confirmed stand-down |
| **ResQ Lab** | Web (the current app) | Team, examiners, police in evaluation | SUMO closed loop, forecasts, ghost replay, B0–B5 results |

### 3.3 Core flow (a single emergency mission)

```text
Call received at hospital desk
  └─ Desk creates Mission (pickup point, category) ─► assigns AMB-07 (nearest by Valhalla matrix ETA)
       └─ Crew app rings, crew accepts ─► EN_ROUTE_SCENE (route + ETA to scene)
            └─ AT_SCENE ─► EMT fills pre-alert (category, triage colour, key vitals, flags)
                 └─ Desk/crew picks destination (ranked by ETA + capability + ED load)
                      └─ TRANSPORTING: ED Board shows "AMB-07 · Chest pain · RED · 9–12 min"
                           ├─ ED acknowledges; optionally triggers cath-lab/stroke team page
                           ├─ Crew taps "Request corridor" ─► nodal officer approves
                           │     └─ junction links fire when ETA to the junction ≤ 120 s
                           │        and propose stand-down after a geofence pass; officer confirms
                           └─ ARRIVED (geofence) ─► HANDED_OVER (ED taps) ─► CLOSED
All timestamps recorded ─► reports: response, on-scene, transport, offload intervals
```

### 3.4 Scope by priority (MoSCoW)

**Must (by the end of the pilot):**

- mission lifecycle and audit trail,
- crew app with resilient background GPS,
- ED board with ETA ranges and pre-alerts,
- desk fleet map,
- Valhalla routing with a Chennai metro extract,
- ETA model with calibrated intervals,
- manual corridor workflow with junction links,
- role-based access control,
- monitoring and backups,
- SUMO closed loop with B0–B5 over 20+ seeds and measured conflicting-green results.

**Should:**

- destination recommendation,
- Graph WaveNet fine-tuned on real traces,
- monsoon and closure handling,
- FHIR export of the pre-alert,
- Tamil voice guidance,
- reports dashboard,
- GPS-trace replay tooling.

**Could:**

- dashcam blockage detection (RF-DETR), as a research track,
- ingesting AIS-140 tracking devices,
- an SRM/SSM-style adapter to a test signal controller,
- live third-party traffic feeds (TomTom or Mappls),
- an iOS build.

**Won't (this academic year):**

- automatic control of real signals without a police MoU,
- clinical decision support or diagnosis,
- direct patient identifiers in the pilot; real clinical attributes require the Stage B gate,
- billing,
- 108/112 government integration,
- CARLA as a deliverable (it becomes optional research, §7.6).

---

## 4. Target architecture

```text
              ┌───────────────── Clients ──────────────────┐
 Crew app ────┤ HTTPS batch GPS + REST │  WebSocket (push)  ├──── ED Board / Desk / Corridor / Lab (React)
 (Expo RN)    └──────────┬─────────────┴─────────┬──────────┘     Junction link (PWA, token URL)
                         ▼                       ▼
                 ┌────────────────── Caddy (TLS, rate limits) ──────────────────┐
                 ▼                                                              ▼
        ┌──────────────── ResQ API (FastAPI, modular monolith) ──────────────────┐   Keycloak
        │ missions │ fleet │ hospitals │ prealerts │ corridor │ eta │ reports │ lab│◄─ (OIDC, RBAC,
        │ audit    │ notifications │ geofence │ fhir-export │ admin               │    orgs/tenants)
        └───┬──────────────┬─────────────────┬───────────────┬──────────────────┘
            │              │                 │               │
     Redis/Valkey    PostgreSQL 17      Valhalla         Workers (Arq)
     • live state    + PostGIS          • route/matrix   • ETA refresh 5 s
     • pub/sub fan-  + TimescaleDB      • isochrone      • map-matching jobs
       out           • missions, audit  • map-match      • forecast → traffic
     • streams       • positions (hyper • live traffic     speeds 5 min
                       table, retention)  speeds         • notifications (FCM,
                                                          SMS, WhatsApp)
            ▲                                     ▲
            │        ┌──────── Intelligence ──────┴─────────────┐
            └────────┤ ETA residual model (LightGBM quantile)   │
                     │ Graph WaveNet segment forecaster (CPU)   │
                     │ Destination ranker │ Corridor JIT timer  │
                     └──────────────────────────────────────────┘
        Signal adapters:  ManualCorridor (police + junction links)  │  SumoTraCI (lab)
                          │  ATCS/ICCC adapter (post-MoU)  │  NTCIP1211/J2735-shaped (research)
        Observability: OpenTelemetry → Prometheus + Grafana + Loki; Sentry (web + mobile); Uptime Kuma
```

**Design rules carried over from the prototype.** These are worth defending in the viva.

1. **Adapters at the edges.** The corridor logic does not know whether it is talking to
   constables, SUMO or an ATCS. This is the existing `adapters/` idea, extended.
2. **ML advises; deterministic code acts.** The corridor safety state machine and the mission
   state machine are plain, tested code.
3. **One contract.** Pydantic models generate the OpenAPI spec, the spec generates the TypeScript
   client, and the same contract is used in all three apps.
4. **Every decision is recorded with its inputs.** That record serves audit, replay, and training
   data.

**Why a modular monolith and not microservices:** there are three developers, one city and one
pilot. One deployable API with clear internal modules is faster to build and easier to secure and
debug. Module boundaries are kept clean (no cross-module table access), so any module can be split
out later.

### 4.1 Repository restructure (incremental, nothing breaks)

```text
resq/                      # Python package (move existing top-level packages in gradually)
  core/ (config, db, auth, audit, events)
  missions/ fleet/ hospitals/ prealerts/ corridor/ eta/ reports/ notifications/ fhir/
  research/ ← existing routing/, fusion/, perception/, experiments/, recorder/ live here
forecast/  sim/            # unchanged, still importable
apps/
  crew/                    # Expo app
  web/                     # current web/ renamed; routes: /ed, /desk, /corridor, /j/:token, /lab
infra/
  compose.yaml, compose.prod.yaml, caddy/, keycloak/realm-export.json,
  valhalla/ (build script for Chennai tiles), grafana/ dashboards, backup/
docs/adr/                  # Architecture Decision Records (one page each)
```

The current Live / Forecast / Replay / Cab / Results pages move under `/lab`. They remain the
academic demo and do not need to be rewritten.

---

## 5. Technology selection

| Concern | Choice | Alternatives considered | Why this choice |
|---|---|---|---|
| API | **FastAPI + Pydantic v2** (keep) | Django, NestJS, Go | Already in use and tested; async WebSockets; OpenAPI for free |
| DB | **PostgreSQL + PostGIS** first; TimescaleDB if needed | MongoDB, InfluxDB | Geo queries, missions and audit are required; partition ordinary PostgreSQL location history first and add TimescaleDB only if retention/query load justifies another extension |
| Migrations / ORM | **SQLAlchemy 2 + Alembic** (or SQLModel on top) | Tortoise, raw SQL | Mature; typed; works with GeoAlchemy2 |
| Cache / bus | **Valkey (Redis-compatible)**: pub/sub + Streams | Kafka, NATS, RabbitMQ | One small dependency covers live state, fan-out and job queue. Kafka is overkill for one city |
| Background jobs | **Arq** (asyncio on Redis) | Celery, Dramatiq | Async-native, tiny, fits FastAPI |
| Routing | **Valhalla** (self-hosted Docker, Chennai metro tiles from the Geofabrik India "southern zone" extract) | OSRM, GraphHopper, keep custom Dijkstra | One engine covers route, matrix (nearest ambulance), isochrone (hospital catchment) and **map matching** (turns crew GPS traces into per-road speeds). It supports historical and live speed data and time-dependent costing. OSRM is faster but weaker on time-dependence and map matching. **Spike in week 3** to confirm live-speed updates on the current release |
| Auth | **Keycloak** (OIDC, Organizations for hospitals as tenants) | Zitadel, Auth0, Supabase Auth | Self-hostable (data stays in India), RBAC, MFA, mature. Auth0 adds cost and data residency questions |
| Web | **React 19 + Vite + MapLibre GL** (keep) + **TanStack Query** + **openapi-typescript / openapi-fetch** | Next.js | Keep what works; add typed client and server-state caching |
| Basemap | **Protomaps PMTiles** (Chennai extract, self-hosted) or OpenFreeMap | Google/Mapbox tiles | No per-view fees, works offline in the app, no dependency on a tile vendor. Check Protomaps' commercial terms before any commercial use |
| Mobile | **Expo (React Native, latest SDK)** + `expo-location` + `expo-task-manager` + `@maplibre/maplibre-react-native` + `expo-speech` + `expo-notifications` + `expo-sqlite` (offline queue) | Flutter, native Kotlin | The team already writes TypeScript and React. One codebase. EAS builds. Background location is supported via TaskManager (Android foreground service). Evaluate **Ferrostar** (open-source navigation SDK that speaks Valhalla) if built-in turn-by-turn becomes a priority |
| Live traffic input | **Own fleet probes** (primary) + optional **TomTom Traffic Flow** (free tier about 2,500 calls/day; confirm Chennai coverage) or **Mappls** (Indian provider) | Google Routes | Google remains runtime display only, never stored or trained on (the existing rule, consistent with the Maps terms). Probe data you collect yourself has no licence restrictions |
| Forecasting | **PyTorch Graph WaveNet** (keep) + **LightGBM quantile** ETA residual model + **MLflow** model registry | DeepETA-style transformer, STAEformer | Uber's own path was routing ETA plus gradient-boosted residual before going deep. LightGBM is the right first step on small data |
| Detection (research track) | **RF-DETR** (Apache-2.0 code and COCO weights) | Ultralytics YOLO11/YOLO26 (AGPL-3.0) | AGPL forces open-sourcing the whole product or buying a licence. RF-DETR keeps a commercial path open. YOLO is acceptable for pure research results |
| Notifications | **FCM** (via Expo push) + **SMS via a DLT-registered provider** (MSG91 or Exotel) + **WhatsApp Business Cloud API** for junction links | Twilio | India requires DLT registration of the SMS sender ID and templates. Indian providers handle it |
| Proxy / TLS | **Caddy** | Nginx, Traefik | Automatic HTTPS with almost no config |
| Observability | **OpenTelemetry → Prometheus, Grafana, Loki**; **Sentry** (React + React Native); **Uptime Kuma** | Datadog, New Relic | Free and self-hosted, with crash reporting from phones in the field |
| Testing | pytest, **Schemathesis** (API fuzzing from OpenAPI), **Playwright** (web E2E), **Maestro** (mobile E2E), **k6** (load), SUMO headless scenarios in CI | — | Each layer has a cheap automated check |
| Hosting (pilot) | One VM in an **Indian region** (AWS Mumbai/Hyderabad, Azure Central India, or E2E Networks), Docker Compose, nightly encrypted off-site backups | Kubernetes | Data stays in India and the setup is simple. Move to k3s only if there is more than one city or hospital |
| Interop | **FHIR R4** using the **ABDM/NRCeS Implementation Guide** profiles (v6.5.0 current); `fhir.resources` Python library | HL7 v2 | National standard; makes later HIS/ABDM integration an export, not a rebuild |

### 5.1 Licences to watch

- **OSM (ODbL):** attribution is required (already done). If you distribute a *modified road
  database*, share-alike applies to that database.
- **Google Maps Platform:** storing or caching content is restricted. Keep Google out of storage
  and training (the existing rule).
- **Ultralytics:** AGPL-3.0, as above.
- **IDD (Indian Driving Dataset):** the licence is not clearly stated by third parties. Read the
  official terms before using it in anything commercial.
- **Protomaps basemap:** free for non-commercial use. Check before a commercial pilot.
- **Maps shown in India** must follow the government's boundary representation if national
  borders are visible. A Chennai-only map avoids the issue; do not show country borders.

---

## 6. Domain model and interfaces

### 6.1 Core entities (PostgreSQL)

```text
Organization(id, name, type: hospital|police|operator)
Facility(id, org_id, name, location geography(Point), abdm_hfr_id?, ed_entrance geography(Point),
         capabilities jsonb  -- {cath_lab_24x7, stroke_thrombolysis, trauma_level, nicu, burns}
         status jsonb        -- {ed_load: green|amber|red, diverting: bool, updated_at})
Ambulance(id, org_id, registration, type: BLS|ALS|NEONATAL|TRANSFER, device_id, active)
CrewMember(id, org_id, keycloak_sub, role: driver|emt|coordinator|ed|police|admin, phone_hash)
Mission(id, org_id, ambulance_id, category, priority: P1|P2|P3, pickup geography, pickup_text,
        destination_facility_id, status, created_by, version)
MissionEvent(id, mission_id, at timestamptz, type, actor, payload jsonb)     -- append-only
PositionPing(time timestamptz, ambulance_id, mission_id?, geom, speed, heading, accuracy,
             battery, source: app|vltd|sim)            -- Timescale hypertable, 90-day retention
PreAlert(id, mission_id, age_band, sex?, category, triage: RED|YELLOW|GREEN, vitals jsonb,
         flags: [stemi, stroke_onset_at, trauma_mechanism, ...], free_text?, acked_by, acked_at)
EtaEstimate(time, mission_id, p50_s, p10_s, p90_s, route_version, model_version)
CorridorRequest(id, mission_id, status, requested_by, approved_by, route_geom, expires_at)
CorridorJunction(id, request_id, junction_id, approach_bearing, eta_s, state, notified_at,
                 passed_at, link_token_hash)
Junction(id, name, location, signalised: bool, atcs_id?, police_contact_group)
Closure(id, geom, reason: flood|metro|event|accident, valid_from, valid_to, created_by)
AuditLog(id, at, actor, action, entity, entity_id, before jsonb, after jsonb, ip)  -- append-only
```

### 6.2 Mission state machine (deterministic, tested like `corridor/`)

```text
NEW → ASSIGNED → ACCEPTED → EN_ROUTE_SCENE → AT_SCENE → TRANSPORTING → ARRIVED → HANDED_OVER → CLOSED
  ↘ CANCELLED (any state before ARRIVED)       TRANSPORTING ⇄ DIVERTED (destination change)
```

- Each transition has an allowed actor, and the backend enforces it. An ED nurse cannot set
  `TRANSPORTING`.
- Each transition writes a `MissionEvent`.
- `ARRIVED` is proposed automatically by a geofence of about 60 m around `ed_entrance` and
  confirmed by the crew. This avoids false arrivals at the hospital's main gate.
- Intervals derived from the events: response time (`ASSIGNED→AT_SCENE`), on-scene time,
  transport time, and **offload time** (`ARRIVED→HANDED_OVER`), which hospitals watch closely.
- Missions carry a `version` column so concurrent edits from desk and crew fail safely
  (optimistic locking).

### 6.3 Corridor request state machine

```text
DRAFT → REQUESTED → APPROVED → ACTIVE → COMPLETED
           ↘ DENIED     ↘ EXPIRED (no approval in N min)    ACTIVE → CANCELLED (reroute / mission end)
Per junction: PENDING → NOTIFIED (ETA bound crosses threshold) → HOLDING (authenticated officer records confirmation) → PASSED (geofence proposal) → RELEASED (officer confirms stand-down)
```

**Just-in-time rule.** This replaces "switch at 300 m".

```text
Notify when ETA_p10(junction) ≤ queue_clear_time + human_reaction + safety_margin
```

- The 90–150 s lead time is a hypothesis, not a fixed threshold. Measure reaction and queue-clear
  times in supervised exercises. Use the conservative early-arrival bound, with a cap to avoid
  long traffic holds, and show uncertainty and GPS freshness to the officer.
- Only the next **2–3 junctions** are ever active. This is the existing hysteresis principle.
- A reroute cancels the junctions that are no longer on the route **immediately**, with a
  "STAND DOWN" message.
- **Stale/pass-missed handling:** mark the prediction stale, stop sending countdown updates and
  alert the nodal officer. The officer confirms traffic-control actions and stand-down. The software
  must never imply that an elapsed ETA is authority to release or hold cross traffic.

### 6.4 API surface (v1, versioned under `/api/v1`)

| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/missions` | desk | Create mission |
| POST | `/missions/{id}/assign` | desk | Assign ambulance (returns ranked candidates when no ambulance is given) |
| POST | `/missions/{id}/transition` | crew/ed/desk | State change (`{to, at, client_event_id}`, idempotent) |
| GET | `/missions?status=active` | all (scoped) | Active missions for my organisation or facility |
| POST | `/telemetry/batch` | crew device | Up to 50 GPS pings, idempotent by `(device_id, seq)` |
| POST | `/missions/{id}/prealert` | crew | Create/update pre-alert |
| POST | `/prealerts/{id}/ack` | ed | Acknowledge |
| GET | `/missions/{id}/eta` | all | Current p10/p50/p90 + route |
| GET | `/facilities/rank?mission_id=` | desk/crew | Destination ranking with reasons |
| POST | `/corridors` | crew/desk | Request corridor |
| POST | `/corridors/{id}/decision` | police | Approve/deny |
| GET | `/j/{token}` | junction (token) | Junction view: countdown, approach, stand-down |
| POST | `/closures` | desk/police | Add closure (flood/metro) |
| GET | `/reports/intervals?from&to` | management | Interval statistics, CSV export |
| GET | `/fhir/Bundle/{mission_id}` | integration | FHIR export of encounter + pre-alert |
| WS | `/ws?topics=facility:{id},mission:{id}` | all | Push: positions, ETA, alerts, corridor |

Rules: every write is **idempotent** (client-generated IDs, so retries from flaky networks are
safe), every write is **audited**, and every read is **tenant-scoped**.

### 6.5 FHIR mapping (pre-alert export)

| ResQ | FHIR R4 resource (ABDM IG profiles where available) |
|---|---|
| Mission | `Encounter` (class `EMER`, `period`, `location` history, `serviceProvider`) |
| Patient (pilot: unidentified) | `Patient` with no identifiers, only `gender` and an age extension |
| Vitals | `Observation` (LOINC: HR 8867-4, SpO₂ 59408-5, BP panel 85354-9, RR 9279-1, GCS 9269-2, glucose 2339-0) |
| Triage colour and flags | `Observation` / `Flag` |
| Ambulance | `Location` (mode `kind`, type `AMB`) / `Device` |
| Destination | `Organization` / `Location` with HFR identifier |

Use this as an *export* first (webhook or downloadable Bundle). Validate it with the HL7 FHIR
validator against the NRCeS IG in CI.

---

## 7. The intelligence layer

### 7.1 Routing (Valhalla)

- **Build:**
  - Take the Geofabrik India southern-zone extract and clip it to the Chennai Metropolitan Area
    (`osmium extract`).
  - Apply local patches: Metro diversions, the Gemini flyover, and known one-ways. Keep these as
    OSM-change files in `infra/valhalla/patches/` and review them like code.
  - Build the tiles in CI and publish them as an artifact.
- **Costing:** `auto` with an **emergency profile**:
  - a higher speed factor on arterials,
  - lower penalties for U-turns where legal,
  - a closure avoid-list fed from `Closure` rows.

  Do not route the wrong way down one-ways by default. Indian law gives right of way to emergency
  vehicles, not a licence to drive against traffic. Make it a desk-only toggle.
- **Live speeds:** every 5 minutes, write the forecaster's segment speeds into Valhalla's
  traffic data, mapped OSM way → Valhalla edge with the `way_edges` mapping. Fall back to
  historical profiles. **Week 3 spike:** prove a live-speed update changes an ETA without a tile
  rebuild. If it fails, use OSRM MLD with `osrm-customize --segment-speed-file` for the live layer
  and keep Valhalla for map matching and isochrones.
- **Keep `routing/engine.py`** as the research oracle: the tests compare Valhalla's path cost to
  the Python Dijkstra on the small graph.

### 7.2 ETA model: what the hospital actually sees

```text
ETA_final = Valhalla_ETA(route, depart=now, live speeds) × exp(f(x))   with quantiles p10/p50/p90
```

- **Features:**
  - Valhalla ETA, route length, number of signalised junctions, number of right turns;
  - share of the route on arterials;
  - hour of week, holiday flag;
  - rain in the last hour (Open-Meteo, free) and monsoon season;
  - live segment forecast summary (mean and min speed on route at +5/+15 min);
  - closures nearby;
  - ambulance type, mission priority;
  - corridor active (yes/no);
  - remaining distance (for in-trip updates).
- **Model:** LightGBM with quantile loss (α = 0.1, 0.5, 0.9). Wrap it in **conformalised quantile
  regression** so the 80 % band covers about 80 % of trips. The project already does split-conformal
  intervals for Graph WaveNet, so reuse `forecast/training/calibration.py`.
- **In-trip updates:** recompute every 5 s from the current position. Smooth the displayed value
  (the existing hysteresis idea) so the ED board does not flicker.
- **Cold start:** display the routing baseline plus an interval labelled provisional. Use SUMO
  trips for software testing, not to claim real-world calibration. Fit a learned residual only
  after enough independent real trips exist for training, calibration and held-out testing.
- **Targets:** on real trips of 15 minutes or less, p50 MAE ≤ 90 s and 80 % interval coverage of
  75–85 %. Compare with Valhalla-only on a prespecified held-out set. Any comparison with a
  third-party ETA needs a terms review and a permitted evaluation protocol first.

### 7.3 Segment forecasting on real data (continuing the current work)

1. **Data:** crew-app pings arrive every 1–2 s while moving. Every night, map-match them with
   Valhalla `trace_attributes`, which returns the edges travelled and the time spent on each.
   Aggregate to 5-minute speeds per monitored segment in a Timescale continuous aggregate.
2. **Sparsity:** a few ambulances will not cover every road every 5 minutes. Treat missing as
   *missing* (the masked loss the training code already supports), never as free flow. That
   convention is right for SUMO and wrong for real probes.
3. **Volunteer probes (optional):** a background-tracking build for hospital staff commutes or a
   partner fleet would add coverage. Namma Yatri (an open mobility platform) and taxi fleets are
   worth an approach. Each needs explicit consent.
4. **Transfer:** pre-train on CHENNAI-SIM, then fine-tune on real data. Report real-only versus
   sim-pretrained to show whether simulation helps. That comparison is a publishable result.
5. **Serving:** CPU inference every 5 minutes. Outputs feed Valhalla live speeds (§7.1) and the
   ETA features (§7.2). Register the model in MLflow with dataset hash and git SHA, as the current
   checkpoint metadata already does.

### 7.4 Destination recommendation (decision support, not a decision)

```text
score(facility) = ETA_p50 + penalty(capability mismatch) + penalty(ed_load) + penalty(diverting)
```

- Show the top three with plain reasons, for example: "Apollo Greams Rd: 9 min, cath lab 24×7, ED
  amber".
- The coordinator or EMT chooses, and the choice and reason are logged.
- The ranking is never automatic, which keeps ResQ outside clinical decision-making (§9.4).
- `ed_load` comes from a one-tap ED status toggle (green/amber/red/diverting) on the ED Board.
  It is cheap to build and the most valuable ranking input.

### 7.5 Corridor timing

- The JIT rule in §6.3 uses `ETA_p10` to the junction. For the **manual** mode, measure constable
  reaction time and queue-clear time in drive tests and SUMO.
- For **signal** mode (SUMO/ATCS), keep the existing `IntersectionController`. Add queue
  estimation from SUMO detectors (lab) or from the ATCS (later), and the **queue-debt recovery**
  controller from the original plan.

### 7.6 Perception (research track, may be cut)

The original CARLA + YOLO path cannot be deployed: hospitals will not fit LiDAR, and CARLA output
is not Chennai. If the team has capacity in Phase 4, the deployable version is:

- a **phone or dashcam** facing forward,
- running **RF-DETR-nano** (ONNX/TFLite) on the device,
- fine-tuned on IDD plus about 300 labelled, blurred Chennai frames,
- detecting "stopped vehicles across ≥ 2 lanes" and sending a `HazardReport`, which becomes a
  `Closure` candidate after desk review.

This reuses `BlockageDetector` logic and the fusion override. Faces and number plates must be
blurred on the device before any upload. If time is short, cut this track (§16).

---

## 8. The green corridor: three integration tiers

| Tier | What changes on the road | Needs | When |
|---|---|---|---|
| **T1: Coordinated manual corridor** | Police control room approves; constables get a WhatsApp link with countdown and approach direction; nothing touches the signal | A nodal officer willing to try it; DLT/WhatsApp templates | Pilot (Phase 3–5) |
| **T2: ATCS/ICCC request** | ResQ sends a priority request to the city ICCC/ATCS; the **city's** controller decides and executes; ResQ receives status | GCTP MoU, vendor API documentation, test junction | After the IDP, if the MoU succeeds |
| **T3: Standards-based (NTCIP 1211 / J2735 SRM-SSM)** | Same as T2 over a standard interface | Controller conformance | Research and demo in SUMO only |

**Safety principles for all tiers** (put these in the MoU draft):

- ResQ only **requests**. The signal authority **decides**. Every request has an expiry. In manual
  mode, software expiry marks the request stale; an officer confirms traffic-control stand-down.
- No more than N (= 3) junctions are active per vehicle, and at most one active corridor crosses
  each junction. Requests that conflict between two ambulances escalate to the officer.
- Minimum green, amber and all-red are never shortened. Pedestrian clearance must be validated
  against the imported SUMO signal programs; the controller state machine alone cannot prove it.
- Complete audit: who requested, who approved, every junction's notified, held and released time.

**SUMO closed loop (Phase 3).** This is what turns the academic results into real ones:

1. `SumoTraCIAdapter` drives the corridor module through the same `SignalAdapter` interface. The
   ambulance's `getNextTLS` provides the upcoming junctions, and the controller sets programs
   through TraCI.
2. Use SUMO's **bluelight device** so background vehicles form a rescue lane.
3. Run B0–B5 × 6 scenarios × **≥ 20 seeds** on the real network. This replaces the formula runner
   output in the Results page, and the formula runner stays as a "fast estimate" with a label.
   These are imported-network simulation results, not measured Chennai ambulance outcomes; validate
   network geometry and signal programs before reporting them.
4. Metrics:
   - ambulance travel time (mean, p95, CI),
   - stops,
   - green-on-arrival,
   - cross-street added delay and recovery time,
   - **measured** conflicting-green count, with observed junction-seconds and missing-observation
     coverage; a complete run must have 0 violations before it can be called safe in simulation.
5. Also run **T1 manual mode** in SUMO: a junction "holds" only after the notify time plus a
   sampled human reaction delay. This quantifies how much of the benefit the police can get
   *without* signal integration, which is the most persuasive slide for an MoU.

---

## 9. Security, privacy and compliance

### 9.1 Data minimisation (the main strategy)

- **Stage A stores no real clinical attributes.** It uses synthetic pre-alerts, mission timestamps
  and on-duty ambulance telemetry. Staff location is personal data, and a pickup/time combination
  may become linkable to an encounter. Give staff notice, restrict access, and set retention.
- **Stage B is a separate approval gate.** If the hospital authorises real age bands, triage,
  vitals or flags, treat the combination as potentially identifiable even without names, phone
  numbers or photos. Limit fields and free text, define who may see them and when they are deleted.
- Rounding a pickup point after closure is useful minimisation, but it does not make a live trace
  anonymous. Keep live location access narrow and document the purpose of each retained field.

### 9.2 DPDP Act 2023 and DPDP Rules 2025

- The [official commencement notification](https://egazette.gov.in/WriteReadData/2025/267647.pdf)
  schedules the relevant provisions of the Act 18 months after 13 November 2025; the
  [Rules notification](https://www.meity.gov.in/static/uploads/2025/11/53450e6e5dc0bfa85ebd78686cadad39.pdf)
  staggers individual rules. Recheck both before the pilot and obtain the partner's legal review.
- **Processing for a medical emergency** that threatens life is among the Act's "legitimate uses"
  that do not need consent. Have a lawyer or faculty adviser confirm how this applies before any
  identifiable patient data is collected.
- Crew and staff location data is personal data. Give staff a clear notice, track only
  **on duty** (the app has a duty toggle), and delete pings after 90 days. Aggregates are kept.

### 9.3 Security controls (target: OWASP ASVS Level 2)

- **Authentication and roles:**
  - OIDC via Keycloak, MFA for desk, police and admin.
  - Device-bound refresh tokens for crew phones.
  - Junction links are **single-corridor, short-lived (≤ 30 min), read-only tokens**, and only the
    hash is stored.
- **Tenant isolation:** every query is scoped by `org_id`. Postgres row-level security acts as a
  second layer.
- **Encryption:** TLS 1.3 everywhere; encrypted disks and backups; secrets in environment or SOPS,
  never in git.
- **Records:**
  - Append-only `AuditLog` and `MissionEvent`.
  - Logs kept 180 days in India. CERT-In directions require cyber-incident reporting within
    6 hours and 180-day log retention.
- **Supply chain:** Dependabot/Renovate, `pip-audit`, `npm audit` (already in CI), and container
  scanning (Trivy).
- **Abuse protection:**
  - rate limits on telemetry and auth,
  - telemetry must come from the device assigned to that ambulance,
  - corridor requests need an active P1/P2 mission and police approval. Mission existence alone
    does not prove that a request is legitimate.

### 9.4 Medical-device boundary

ResQ handles logistics, communication and documentation. It must **not**:

- diagnose,
- recommend treatment,
- choose a destination automatically on clinical grounds.

Keep the pre-alert as structured data entry and the ranking as transparent decision support with a
human choice. Do not assume this settles medical-device classification; confirm intended-use
language and obligations with the partner hospital's quality and legal team before live use.

### 9.5 Road safety

- **The driver must not interact with the phone while moving.** The cab UI has large glanceable
  elements and voice guidance (Tamil/English). All data entry is done by the EMT or while
  stationary. The app locks forms above 10 km/h for the driver role.
- Corridor alerts never tell a constable to "go". They show *when* and *from which direction*;
  traffic control stays the officer's judgement.

### 9.6 Ethics approval

If the pilot records any patient attribute linked to real encounters (even de-identified vitals)
for *research publication*, obtain the hospital's **Institutional Ethics Committee** approval under
the ICMR National Ethical Guidelines. Shadow mode with only ambulance telemetry and timestamps may
qualify for an exemption or expedited review. **Ask in the first meeting** (§14), because approval
can take 4–8 weeks.

---

## 10. Reliability and operations

### 10.1 Service level objectives (pilot)

| SLO | Target |
|---|---|
| API availability (06:00–24:00) | 99.5 % |
| GPS ping → ED board update latency | p95 ≤ 3 s |
| Pre-alert → ED push/audible alert | p95 ≤ 5 s; SMS fallback ≤ 30 s |
| Data loss across a 5-minute connectivity gap | 0 pings (offline queue) |
| Background tracking survival on a Xiaomi/Oppo/Vivo phone over an 8-hour shift | ≥ 99 % of on-duty minutes covered |

### 10.2 Failure modes and responses

| Failure | Detection | System behaviour | Human fallback |
|---|---|---|---|
| Phone loses network (underpass, flyover) | Ping gap > 20 s | ED board shows "last seen 35 s ago", ETA uses dead reckoning along the route, and the band widens | Crew calls ED (number in app) |
| App killed by OEM battery manager | Heartbeat missing while on duty | Push wake-up attempt; desk alert "AMB-07 tracking lost" | On-boarding checklist whitelists the app (dontkillmyapp steps per brand) |
| Valhalla down | Health check | Last known route kept; straight-line ETA marked "degraded" | Desk sees banner |
| Forecaster stale (> 15 min) | Model heartbeat | ETA falls back to Valhalla historical speeds, flagged | None needed |
| Server down | Uptime Kuma → SMS to on-call | Crew app keeps navigation offline (route cached) and queues data | Phone call workflow, which is what happens today |
| Wrong arrival detection | Crew must confirm | Geofence only *proposes* ARRIVED | Desk can correct (audited) |
| Corridor junction never passed | ETA deadline or stale GPS | Mark countdown stale and escalate to the nodal officer | Officer confirms stand-down and traffic-control actions |
| Duplicate/out-of-order events | `client_event_id`, timestamps | Idempotent; state machine rejects illegal transitions | — |

**The cardinal rule:** ResQ failing must leave the hospital **no worse off than today**. Every
feature degrades to the current phone-call workflow.

### 10.3 Operations

- **Deploys:** Docker Compose on one VM; `main` → staging automatically, tags → production with a
  manual approval. Database migrations run before the app starts; rollbacks are rehearsed.
- **Backups:** nightly `pg_dump` plus WAL archiving (pgBackRest) to off-site object storage in
  India. A **restore is tested monthly**.
- **Dashboards:**
  - live missions,
  - ping latency,
  - tracking coverage per ambulance,
  - ETA error (rolling),
  - notification delivery,
  - error rates.
- **Runbooks:** "tracking lost", "server down during a mission", "suspected data breach (6-hour
  CERT-In / 72-hour DPDP clock)", "wrong ETA complaint".
- **On-call during the pilot:** one team member per day, with a phone.

---

## 11. Testing and validation strategy

| Level | What | Tooling | Gate |
|---|---|---|---|
| Unit | State machines (mission, corridor, signal), ETA features, scoring | pytest, Hypothesis (property tests: "no illegal transition is ever accepted") | CI |
| Contract | API matches OpenAPI; TS client compiles | Schemathesis, `openapi-typescript` diff | CI |
| Integration | API + Postgres + Valkey + Valhalla in containers | pytest + Testcontainers / compose | CI (nightly for Valhalla) |
| Simulation | SUMO closed loop: 3 short scenarios headless per PR; full B0–B5 × 20 seeds weekly | `sim/` + experiment runner | CI / scheduled |
| **Trace replay** | Recorded real GPS drives replayed through the whole stack at 1×–20× | New `tools/replay_trace.py` (extends `recorder/`) | Before each release |
| Web E2E | ED board receives pre-alert; desk assigns mission | Playwright | CI |
| Mobile E2E | Login → accept → status → pre-alert, offline/online toggle | Maestro on emulator + 2 real low-end Android phones | Before each build |
| Load | 50 ambulances × 1 Hz, 20 ED boards, 5 corridors | k6 | Before pilot |
| Field | Drive tests (§12, Phase 2 and 4) | Team vehicle + phones | Phase exit |
| Usability | ED staff, drivers, coordinator, police | Think-aloud sessions, **SUS questionnaire** (target ≥ 75), task time | Phase exit |
| Security | ASVS L2 checklist, ZAP baseline scan, dependency audit, tenant-isolation tests | OWASP ZAP, pip-audit, Trivy | Before pilot |

**Simulated fleet.** A `sim-driver` worker publishes realistic pings along Valhalla routes, with
noise and dropouts (the existing `sim/probes/generator.py` logic). It powers demos, staff training
and load tests without a real ambulance. This is the "digital twin" mode.

---

## 12. Phased execution plan (31 weeks)

> Check these weeks against your university calendar: semester exams, Review III and final review
> dates, and the Pongal break (about 14–17 January 2027). Each phase ends with a demo and an exit
> gate. If a gate fails, apply the scope cuts in §16 before moving on.

Roles used below (§13): **P** = Platform & backend lead, **A** = Apps & UX lead, **I** =
Intelligence & simulation lead.

### Phase 0: Stabilise and discover (Weeks 1–2, 12–25 Oct 2026)

| Who | Tasks |
|---|---|
| All | **Discovery interviews (target 8–12)**:<br>• ED head or charge nurse at 2 hospitals<br>• ambulance coordinator<br>• 2–3 drivers and EMTs<br>• one GCTP traffic officer, if reachable through faculty or the college<br>• one 108 crew member<br>Use a fixed script (Appendix B). Synthesise the findings into a one-page "what we learned" |
| All | Identify and approach the **pilot partner**: a private or teaching hospital with 3–10 ambulances; faculty introductions; the college's own hospital, if any. Draft a one-page proposal and a data-sharing note (Appendix C) |
| P | Review and commit the pending forecast work with its author. Fix D7/D8 (repo hygiene, naming). Fix **D1** (explicit clock) with tests. Write a short ADR for the first vertical slice and staged pilot data; add other ADRs when decisions are made |
| I | Mark D2 as unknown until measured; define the SUMO phase observation and coverage test. Put SUMO in CI headless (a 60-second scenario) if the runner is stable |
| A | Draft low-fidelity flows (paper or Figma) for crew, ED board and junction link. Test them with interviewees in week 2 |

**Exit gate:** at least 6 interviews done; a pilot partner has had at least one conversation;
flows revised from the feedback; tests green; Stage A data fields and access agreed in writing.
If partner access is delayed, proceed with synthetic/drive-test work and mark the gate incomplete.

### Phase 1: Platform foundation (Weeks 3–6, 26 Oct – 22 Nov)

| Who | Tasks |
|---|---|
| P | Build the first vertical slice: Postgres+PostGIS, migrations for mission/event/position/role data, idempotent mission transitions and telemetry, audit, scoped API reads, and a basic ED acknowledgement. Integrate OIDC before any partner login. Add Valkey fan-out after a multi-viewer load check; add TimescaleDB only if ordinary partitions prove inadequate |
| I | **Week 3 Valhalla spike** (Chennai tiles, emergency costing, live speed update, `trace_attributes` map matching), producing an ADR. Valhalla client module; ETA endpoint v0 (Valhalla only). Sim-driver worker publishing to `/telemetry/batch` |
| A | Set up the Expo project (TypeScript, EAS dev build, Sentry, i18n with English and Tamil keys). Generated API client in web and mobile (D6). Web shell with routes `/ed`, `/desk`, `/corridor`, `/lab` (move current pages to `/lab`) |

**Exit gate:** a simulated ambulance drives a route in Chennai, and its position and baseline ETA
update on a bare ED page behind a login. A desk-to-crew-to-ED mission can close with a complete
event audit; tenant isolation and idempotent retries pass integration tests. Valhalla remains a
separate spike if it is not ready for this slice.

### Phase 2: Crew app + ED board MVP (Weeks 7–10, 23 Nov – 20 Dec)

| Who | Tasks |
|---|---|
| A | **Crew app:**<br>• login and duty toggle<br>• mission inbox with ringing alert<br>• accept and big status buttons<br>• route map with maneuver list and `expo-speech` voice in Tamil/English<br>• background location via TaskManager (foreground-service notification on Android)<br>• **offline queue in SQLite** with batched upload<br>• 4-tap pre-alert: category → triage colour → vitals keypad → flags<br>• "open in Google Maps" fallback<br><br>**ED Board:**<br>• inbound list sorted by ETA, with p10–p90 band<br>• pre-alert cards and acknowledge<br>• audible alert distinct by triage colour<br>• wall-TV mode<br>• "last seen" staleness indicator |
| P | Notifications service (Expo push; SMS provider account; start **DLT registration** now, since it takes weeks). Desk v0 (fleet map, create and assign missions). Geofence ARRIVED proposal. Interval reports v0 |
| I | ETA v1: Valhalla baseline with an explicitly provisional interval; no bias correction claimed from sim trips. **Drive-test protocol** (Appendix D). Run the first **20 drive tests** in a team vehicle at different hours (normal driving, not emulating an ambulance). Record trace, Valhalla ETA and actual time |

**Exit gate (Review III demo):** a real phone in a real car runs a full test mission. The ED board
shows a synthetic pre-alert and a live, provisionally labelled ETA band; the mission closes and the
report shows the intervals.
Background tracking survives screen-off for 30 minutes on a low-end Android phone.

### Phase 3: Corridor + SUMO closed loop (Weeks 11–15, 21 Dec – 24 Jan, includes holidays)

| Who | Tasks |
|---|---|
| P | Corridor module: request → approve → active. Junction catalogue (signalised and manned junctions in the pilot area, from OSM plus a site survey). JIT notifier worker. **Junction link PWA** (no install, token URL, big countdown, approach arrow, STAND-DOWN). WhatsApp Business Cloud API templates submitted. Corridor audit |
| A | Corridor control-room page (approve/deny, live map, junction states). Crew "Request corridor" button (disabled unless P1/P2). ED board shows corridor status. Usability session #1 with 2 ED staff and 2 crew (SUS) |
| I | **SUMO closed loop:**<br>• `SignalAdapter` interface; TraCI implementation using the existing `IntersectionController`<br>• bluelight device for the rescue lane<br>• manual-mode (T1) model with human reaction delay<br>• B0–B5 × 6 scenarios × 20 seeds on the real network<br>• replace the formula numbers on the Results page (the formula runner keeps a "fast estimate" label) |

**Exit gate:** a lab or closed-site corridor dry run with 2 team members playing junction roles,
receiving links and confirming passes. Public-road observation requires police agreement and does
not involve traffic control by the team. SUMO results have confidence intervals and 0 measured
conflicting greens with complete phase-observation coverage.

### Phase 4: Intelligence on real data (Weeks 16–20, 25 Jan – 28 Feb)

| Who | Tasks |
|---|---|
| I | Nightly map-matching pipeline → Timescale continuous aggregate of 5-minute segment speeds. ETA v2: LightGBM quantile + conformal calibration, evaluated on held-out drive tests and on shadow-pilot trips once they start. Graph WaveNet fine-tune (sim-pretrained versus real-only) on the monitored segments, if coverage is sufficient. Weather (Open-Meteo) and closure features. MLflow registry |
| P | Destination ranking endpoint + ED status toggle. Closures UI (desk/police) with expiry. FHIR export Bundle + validator in CI. Security hardening pass (ASVS checklist, ZAP, RLS, rate limits). Load test with k6 |
| A | Desk v1 (ranking display with reasons, closures, history). Reports dashboard (intervals, ETA accuracy, alert lead time) with CSV export. Pilot onboarding kit: install guide, OEM battery whitelisting per brand, a 1-page laminated cab card. Usability session #2 |
| *Optional* | Research track (§7.6): RF-DETR on IDD + Chennai frames. **Start only if Phase 3 exited on time** |

**Exit gate:** report ETA baseline error and interval coverage on held-out real trips. Promote ETA
v2 only if it beats Valhalla-only on a prespecified, independent test set without widening the band
beyond its usability limit; otherwise retain the baseline and continue collecting data. A security
checklist is complete and the partner holds a Stage A / Stage B go/no-go meeting.

### Phase 5: Shadow pilot (Weeks 21–25, 1 Mar – 4 Apr)

| Week | Activity |
|---|---|
| 21 | After partner approval, install on 2–4 ambulances; 1-hour training for crews, ED and desk; dry runs with the simulated fleet |
| 22–24 | **Stage A shadow mode:** authorised on-duty telemetry, mission timing and synthetic alerts alongside normal practice. Staff rely on existing practice. Team on call daily, weekly feedback and controlled bug fixes. **Stage B:** only if the partner approves clinical attributes and the ethics pathway, enable real pre-alerts with restricted access |
| 24 | If the nodal officer agrees: **1–3 T1 corridor trials** on non-critical transfers, with prior approval and an officer present |
| 25 | Pilot close-out: interviews, SUS, data freeze, retrospective |

Measured in Stage A (potentially linkable staff/mission data):

- ETA error and band coverage,
- synthetic-alert delivery and acknowledgement latency,
- offload time,
- tracking coverage,
- notification delivery,
- crashes,
- staff SUS.

Stage B adds real pre-alert lead time and share of arrivals pre-alerted, if approved. Report the
sample size and missing data for every metric; never present Stage A synthetic-alert performance
as clinical readiness.

Door-to-treatment effects need clinical data and a longer study, so state them as future work.

**Exit gate:** report the actual number of authorised missions or field trials, tracking coverage,
failures and safety incidents; a pilot report is drafted. Treat 30 missions as a recruitment target,
not a condition for declaring an unsafe or unapproved data collection successful.

### Phase 6: Evaluation, write-up, handover (Weeks 26–31, 5 Apr – 16 May)

| Who | Tasks |
|---|---|
| I | Final analysis:<br>• SUMO B0–B5 (sim)<br>• T1 manual corridor benefit (sim + trials)<br>• ETA (real)<br>• forecaster transfer (sim → real)<br>Every number labelled with its source (sim, drive test, or pilot) |
| P | Production readiness documentation: architecture, ADRs, runbooks, DPDP readiness checklist (the core duties begin about May 2027), restore drill evidence |
| A | Final demo script:<br>• live crew phone → ED board → corridor junction link<br>• the `/lab` SUMO comparison<br>Video recording as a fallback |
| All | Thesis/report; conference paper draft (for example IEEE ITSC, COMSNETS, or an Indian transport/health-informatics venue); MoU draft for GCTP (T2); sustainability plan (§18) |

**Buffer:** week 31 is deliberately light. Use it for slips.

---

## 13. Team roles (3 people)

| Role | Owns | Also contributes to |
|---|---|---|
| **P: Platform & backend** | API modules, DB, auth, security, infra, notifications, corridor backend, FHIR | ADRs, load tests, on-call rota |
| **A: Apps & UX** | Crew app, ED board, desk, corridor UI, junction PWA, i18n, usability studies, onboarding kit | Discovery interviews (lead), demo |
| **I: Intelligence & simulation** | Valhalla build and costing, ETA model, forecaster, map matching, SUMO closed loop, experiments, drive tests, evaluation | Destination ranking, data pipeline |

Shared rules:

- Every PR is reviewed by one other member, so each person understands each module (a viva
  requirement in the earlier notes).
- Each member demos their own module at every review.
- Weekly 30-minute planning; GitHub Projects board; one ADR for every significant decision.

---

## 14. The pilot: how to get and run it

1. **Who to approach.** In order of likelihood:
   - a teaching hospital linked to the college or faculty,
   - a mid-size private hospital with its own ambulances,
   - a private ambulance operator that serves several hospitals.

   Large chains (Apollo, the hospital in the study area) are worth a letter but have slow
   procurement and their own IT.
2. **What to offer.** Free Stage A shadow software using authorised telemetry and synthetic
   alerts, no change to normal care, and a report of operational intervals. Discuss Stage B
   clinical fields separately with the hospital and its ethics/quality teams.
3. **What to ask for.**
   - A clinical champion (ED head) and an operations champion (ambulance in-charge).
   - Permission to install on 2–4 ambulances.
   - Ten minutes of each crew's time for training.
   - Their ethics-committee guidance (§9.6).
4. **Agreement.** A short pilot MoU or letter with:
   - purpose,
   - data list (Appendix C),
   - retention (90 days raw, aggregates kept),
   - security summary,
   - no-liability and advisory-only clauses (faculty or legal cell to review),
   - right to stop at any time.
5. **Police.** Approach through the college or the hospital's existing green-corridor contact. Ask
   for an **observer**, not an integration: a demonstration of T1 in SUMO and one supervised trial.
6. **If no partner by week 10:**
   - run the pilot with **simulated missions on real roads**: team vehicles, a faculty member as
     "ED", and a mock ED board in a lab;
   - report it honestly as a field trial, not a hospital pilot.

---

## 15. Evaluation plan and KPIs

| Question | Metric | Source | Target / comparison |
|---|---|---|---|
| Can the ED trust the ETA? | p50 MAE, p90 error, 80 % band coverage | Drive tests + pilot | MAE ≤ 90 s on trips ≤ 15 min; coverage 75–85 %; beats Valhalla-only |
| Does the ED get warned early? | Real pre-alert lead time, % arrivals pre-alerted | Stage B only, if approved | Median ≥ 8 min; ≥ 70 % of P1/P2 missions |
| Is it fast and reliable? | Ping→board latency, tracking coverage, push delivery | Telemetry | §10.1 SLOs |
| Do people find it usable? | SUS, task time, error count | Usability sessions | SUS ≥ 75; pre-alert ≤ 60 s |
| Does the corridor help, and how much without signal control? | Travel time, stops, cross-traffic delay, recovery (B0–B5, T1-manual) | SUMO ≥ 20 seeds | Report with 95 % CI; 0 measured conflicting greens with complete phase-observation coverage |
| Does simulation help real forecasting? | Fine-tuned versus real-only MAE | Real probe data | Report either way (a negative result is still a result) |
| Is it safe? | Incidents, near-misses, false arrivals, stuck junctions | Pilot logs | 0 safety incidents |

Continue the existing integrity rules: every number states its source, seed and model version;
simulated numbers are never reported as Chennai measurements.

---

## 16. Risks and scope cuts

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| No pilot hospital | Medium | High | Start in week 1; several candidates; field-trial fallback (§14.6) |
| Police unwilling to engage | High | Medium | T1 is useful as a *demo* and in SUMO; the hospital product does not depend on it |
| Background GPS unreliable on Indian phones | High | High | Foreground service, OEM whitelisting kit, heartbeat alerts, test on 3 brands in Phase 2 |
| Too little real data for ML | High | Medium | Forty drive tests are a feasibility sample, not a reliable train/calibration/test set. Keep the baseline unless independent real data are sufficient; Graph WaveNet fine-tune is optional |
| Valhalla live-traffic integration harder than expected | Medium | Medium | Week 3 spike; OSRM fallback for live layer |
| DLT/WhatsApp approval delays | Medium | Low | Apply in Phase 2; push notifications and plain links work in the meantime |
| Ethics approval delay | Medium | Medium | Run Stage A only after partner approval; keep Stage B clinical attributes disabled until the ethics path is resolved |
| Scope creep (CARLA, perception, iOS) | High | High | MoSCoW (§3.4); research track only after Phase 3 exit |
| Exams / team availability | High | Medium | Light weeks around exams; buffer week 31; every module has a second reviewer |
| Liability concerns from partner | Medium | High | Advisory-only, shadow mode, human confirmation everywhere, audit trail |

**Cut order if behind schedule** (cut from the top):

1. perception research track,
2. Graph WaveNet real fine-tune (keep the ETA model),
3. FHIR export,
4. destination ranking (keep the ED status toggle),
5. corridor WhatsApp delivery (keep SMS/link),
6. Tamil voice (keep a Tamil UI).

**Never cut:**

- offline-safe tracking,
- the audit trail,
- the mission state machine,
- the ETA band,
- the SUMO closed loop with measured safety.

---

## 17. Budget (rough, for the academic year)

| Item | Estimate | Notes |
|---|---|---|
| Cloud VM (4 vCPU / 16 GB, Indian region) staging + prod | ₹0–10,000 / month | Student credits (GitHub Student Pack, Azure for Students, AWS Educate) can cover most of it |
| Object storage + backups | < ₹500 / month | |
| Domain + DNS | about ₹1,000 / year | |
| SMS (DLT) | a few paise per SMS + one-time registration effort | Exact rates vary by provider; budget ₹1–2k for the pilot |
| WhatsApp Business conversations | Low for pilot volumes | Check current Meta pricing for utility templates in India |
| Test phones | Use own or borrowed low-end Androids | Need at least one Xiaomi/Redmi, one Oppo/Realme or Vivo, one Samsung |
| Fuel for drive tests | ₹3–6k | About 40 trips |
| Phone mounts + chargers for pilot ambulances | ₹2–4k | |
| **Total** | **About ₹20–40k** | Mostly covered by credits; check for department or IDP funds |

---

## 18. Beyond the IDP: the path to real deployment

1. **Pilot → paid or sponsored deployment** with the partner hospital (licensed or CSR-funded),
   with interval reports as the value proof.
2. **Incubation and grants.**
   - The IIT Madras HTIC MedTech Incubator is a BIRAC BIG partner. BIRAC's BIG scheme gives up to
     ₹50 lakh over 18 months; calls usually open twice a year, and a company must be registered.
   - Also look at Startup TN schemes and the college's incubation cell.
3. **Police MoU (T2).** Bring the SUMO results, the T1 trial logs and Bengaluru's B-ATCS EVP as
   precedent, and propose a 3–5 junction test on the hospital's approach roads via the ICCC.
4. **Public-system integration.** Reach the 108 service through Tamil Nadu Health Systems/EMRI,
   and ERSS-112 through state CAD (other states integrate ambulances through APIs).
5. **Health-stack integration.** ABDM HFR IDs for facilities, a FHIR push to hospital HIS systems,
   and NABH emergency indicators from the reports module.
6. **Compliance before going commercial:**
   - full DPDP compliance (in force about May 2027),
   - VAPT by a CERT-In empanelled auditor,
   - a formal decision on the medical-device classification,
   - commercial licences for map tiles and models.

---

## 19. The next 14 days (concrete checklist)

- [ ] Review the existing uncommitted forecast changes with their author and commit them when
      ready (`sim/chennai/forecast_dataset.py`, `docs/TRAFFIC_FORECASTING_RUN.md`,
      `web/src/ForecastPage.tsx`).
- [ ] Move `.pptx`, `.pdf` and `trips.trips.xml` out of the repo root (to `deliverables/` with Git
      LFS, or outside the repo); standardise the name "ResQ".
- [x] Fix D1 (explicit clock in `corridor/state_machine.py`) and represent unmeasured D2 safety
      values as unknown, with tests.
- [ ] Wire SUMO phase observations, verify observation coverage, and only then report the D2
      conflicting-green count.
- [ ] Write the interview script (Appendix B) and book 8+ interviews; ask faculty for hospital
      introductions.
- [ ] Send the one-page pilot proposal to at least 3 hospitals.
- [ ] Write ADR-001 to ADR-005.
- [ ] Draw the crew / ED-board / junction-link flows on paper; test them in 2+ interviews.
- [ ] Reserve week 3 for the Valhalla spike (download the Geofabrik southern-zone extract; check
      Docker resources).
- [ ] Open accounts that take time: SMS provider + DLT entity registration, Meta Business
      verification, a cloud account with student credits.
- [ ] Put the university review dates into this plan and adjust phase boundaries.

---

## Appendix A: Mapping existing modules to the new system

| Existing | Becomes |
|---|---|
| `schema/models.py` | Split: research contracts stay; new `resq/*/schemas.py` per module; one OpenAPI |
| `corridor/state_machine.py` | Core of the signal-mode corridor (SUMO/ATCS); plus a new manual-mode junction state machine |
| `routing/engine.py` | Research oracle and test reference for Valhalla |
| `fusion/engine.py` | ETA-feature fusion (forecast + live probes + hazard reports); blockage override → closure candidate |
| `forecast/` | Unchanged training; runtime gains a "real probes" dataset and pushes speeds to Valhalla |
| `sim/probes/generator.py` | Sim-driver worker (synthetic fleet) |
| `sim/chennai/*` | Lab: SUMO closed loop and dataset generation |
| `recorder/` | Trace replay tooling + run store for experiments |
| `adapters/` | `SignalAdapter` (manual / SUMO / ATCS), `TrafficFeed` (probes / TomTom / Mappls / Google runtime) |
| `web/src/*` | `/lab` routes; shared map components reused by ED board and desk |
| `experiments/runner.py` | Kept as a labelled "fast estimate"; SUMO runner produces reported results |

## Appendix B: Discovery interview script (30 min)

1. Walk me through the last emergency arrival you handled, from first phone call to handover.
2. When do you first learn a patient is coming? What do you know at that moment? What do you wish
   you knew?
3. How often is the arrival time you are told wrong? What happens when it is?
4. What do you prepare before arrival for chest pain / stroke / trauma? How much warning do you
   need for each?
5. (Crew) How do you choose the route? What slows you down most? Which junctions or roads?
6. (Crew) Which phone do you use? Does it stay on all shift? Mobile data coverage problems?
7. (Coordinator) How do you track ambulances today? What records do you keep, and for whom?
8. (Police) How is a green corridor requested and executed today? Who decides? What goes wrong?
9. What would make you stop using a new system within a week?
10. Who else should we talk to?

Record notes, not audio, unless the interviewee consents. Store no patient details.

## Appendix C: Pilot data inventory

| Data | Purpose | Retention | Identifiable? |
|---|---|---|---|
| Ambulance GPS pings (on duty, Stage A) | Tracking, ETA | Proposed 90 days raw; approve with partner | Yes: crew location, potentially linked to a mission |
| Mission timestamps and status (Stage A) | Intervals, reports | Agree with partner before collection | Potentially linkable |
| Synthetic pre-alert (Stage A) | Interface and delivery test | Short test retention | No real encounter data |
| Real pre-alert (Stage B approval only) | ED readiness | Define in Stage B agreement | Potentially identifiable even without direct identifiers |
| Pickup point (Stage A) | Routing | Round or delete after close per agreement | Potentially linkable while live |
| Staff accounts (name, role, phone) | Login, notifications | Duration of pilot | Yes (staff) |
| Corridor/junction events | Audit, evaluation | Agree with partner/police | Potentially linkable to a mission |
| App crash logs | Reliability | Proposed 90 days | Device ID may link to staff |

## Appendix D: Drive-test protocol

- **Routes:** 5 fixed origin–destination pairs ending at the partner hospital's ED entrance, plus
  5 random ones.
- **Times:** 08:00–10:00, 12:00–14:00, 17:00–20:00 and 22:00–23:00, on weekdays and weekends;
  include rain if it happens.
- **Driving:** normal driving within the law. **Never** imitate an emergency vehicle.
- **Record:**
  - the ResQ trace at 1 Hz,
  - the Valhalla ETA at departure,
  - ResQ ETA updates every 30 s,
  - a third-party ETA only if its terms permit the intended comparison and retention,
  - actual arrival time,
  - notes on incidents and closures.
- **Target:** 40 trips by the end of Phase 4, enough for a first baseline check but not assumed
  sufficient to train and independently calibrate the learned ETA model.

---

## Sources

Real-world context
- [Chennai AI adaptive signals at 165 junctions, Telangana Today](https://telanganatoday.com/chennai-to-roll-out-ai-powered-adaptive-traffic-signals-at-165-junctions)
- [ITMS overview, Insights IAS (Oct 2026)](https://www.insightsonindia.com/2026/10/01/the-intelligent-traffic-management-system-itms/)
- [ICCC green corridor use case, NIUA](https://iccc.niua.org/iccc/sector/use-case/815e6212def15fe76ed27cec7a393d59)
- [Bengaluru ATCS case study, Indian Infrastructure (Apr 2026)](https://indianinfrastructure.com/2026/04/06/smart-mobility-a-case-study-of-the-bengaluru-adaptive-traffic-control-system/)
- [Bengaluru 163 junctions AI adaptive signals, South First](https://thesouthfirst.com/news/bengaluru-163-traffic-junctions-to-be-upgraded-with-ai-based-adaptive-signal-system)
- [Bengaluru green corridors 2023, South First](https://thesouthfirst.com/karnataka/bengaluru-traffic-police-created-22-green-corridors-for-critically-ill-and-injured-patients-vital-organs-in-2023)
- [Chennai police green corridor initiative, Governance Now](https://www.governancenow.com/news/regular-story/chennai-police-sets-bar-high-green-corridor-initiative)
- [India's green corridors, Open Magazine](https://openthemagazine.com/india/when-a-heart-gets-the-right-of-way-how-indias-green-corridors-turn-traffic-into-lifelines)
- [Apollo Chennai transplants with green corridor, Medical Dialogues](https://health.medicaldialogues.in/health/apollo-hospitals-chennai-performs-life-saving-transplants-with-green-corridor-support-165870)
- [Green corridor explainer, Esri India](https://www.esri.in/en-in/newsroom/blog/green-corridor-for-ambulances)
- [TN real-time ambulance tracking app, Digital Health News](https://www.digitalhealthnews.com/tamil-nadu-to-introduce-real-time-ambulance-tracking-app)
- [108 response times, DTNext](https://www.dtnext.in/news/tamilnadu/overall-response-time-of-108-ambulances-drops-in-last-one-year-727237)
- [CAG audit 2026, Chapter III](https://cag.gov.in/uploads/download_audit_report/2026/Chapter-III-06a87dc3085f1d2.26085793.pdf)
- [Bihar 102 integration with ERSS 112](https://www.pressreader.com/india/hindustan-times-ranchi/20240416/281689734854076)
- [Haryana 108 integration with ERSS](https://www.tribuneindia.com/news/haryana/dial-108-to-be-integrated-with-erss-431887)

Clinical evidence
- [Pre-hospital ECG + notification meta-analysis, PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9072100)
- [Cath lab pre-activation, ACC](https://www.acc.org/about-acc/press-releases/2018/09/17/14/08/pre-activating-cath-labs-prior-to-stemi-arrival-speeds-treatment-reduces-risk)
- [STEMI notification and D2B, EM-Consulte](https://em-consulte.com/article/1069722/stemi-notification-by-ems-predicts-shorter-door-to)
- [Wisconsin Coverdell stroke programme poster](https://wha.org/2020WICoverdellStrokeProgramPoster)

Standards and signal priority
- [SAE J2945/B, TSPP minimum requirements](https://www.dinmedia.de/en/standard/sae-j-2945-b/397728899)
- [NTCIP 1211 explained, LYT](https://lyt.ai/blog/ntcip-1211-what-is-it-and-why-does-it-matter)
- [Miovision Signal Assist, Samsara marketplace](https://www.samsara.com/resources/marketplace/miovision)
- [Iteris priority/preemption](https://www.iteris.com/oursolutions/priority-preemption)

Technology
- [OSRM command-line tools v26.5](https://project-osrm.org/docs/v26.5.0/tools)
- [Mapzen speed tiles (Valhalla traffic design)](https://mapzen.com/blog/speed-tiles/)
- [Self-hosted routing engines guide 2026](https://www.pistack.xyz/posts/2026-04-25-graphhopper-vs-osrm-vs-valhalla-self-hosted-routing-engines-guide-2026/)
- [Expo TaskManager (SDK 58)](https://docs.expo.dev/versions/v58.0.0/sdk/task-manager/)
- [RF-DETR is Apache 2.0, Roboflow](https://blog.roboflow.com/rf-detr-is-free-to-use-commercially/)
- [Ultralytics alternatives 2026, Lightly](https://lightly.ai/blog/best-ultralytics-alternatives-in-2026)
- [YOLO26, Roboflow](https://blog.roboflow.com/yolo26/)
- [Uber DeepETA](https://www.uber.com/en-CA/blog/deepeta-how-uber-predicts-arrival-times/)
- [DeeprETA paper](https://arxiv.org/pdf/2206.02127)
- [Protomaps](https://protomaps.com/)
- [Self-hosting maps with Protomaps, Supabase](https://supabase.com/blog/self-host-maps-storage-protomaps)
- [EMQX vs NATS](https://www.emqx.com/en/resources/emqx-vs-nats)
- [TomTom Traffic API market coverage](https://developer.tomtom.com/traffic-api/documentation/product-information/market-coverage)
- [TomTom pricing](https://developer.tomtom.com/pricing)
- [Mappls APIs](https://mapmyindia.in/move)
- [Google Maps Platform India pricing](https://developers.google.com/maps/billing-and-pricing/pricing-india?hl=de)
- [Google Maps service terms](https://cloud.google.com/maps-platform/terms/maps-service-terms/index-20240422)

Regulation and interoperability
- [DPDP Rules 2025 notified, Storyboard18](https://www.storyboard18.com/digital/breaking-govt-notifies-final-dpdp-rules-sets-staggered-rollout-with-key-obligations-for-data-fiduciaries-84201.htm)
- [DPDP Act in force, Hogan Lovells](https://www.hoganlovells.com/en/publications/indias-digital-personal-data-protection-act-2023-brought-into-force-)
- [DPDP Rules operational guide, iPleaders](https://blog.ipleaders.in/dpdp-rules-2025-operational-compliance-guide-for-indian-businesses/)
- [ABDM FHIR Implementation Guide, NRCeS](https://nrces.in/ndhm/fhir/r4/)
- [TRAI DLT regulations, WebEngage docs](https://docs.webengage.com/docs/trai-sms-dlt-regulations-india)
- [MSG91 DLT template approval](https://msg91.com/help/dlt-registration-in-india/get-approval-for-your-sms-content-on-dlt-platform)
- [IDD dataset, IIIT Hyderabad](https://inai.iiit.ac.in/domains/idd.html)

Funding
- [BIRAC BIG call](https://www.indiascienceandtechnology.gov.in/announcementsopportunity/birac-call-proposal-under-biotechnology-ignition-grant-big-scheme)
- [IIT Madras HTIC MedTech Incubator, BIG partner](https://htic.iitm.ac.in/mti/grant/)

*Items marked "spike", "confirm" or "check" are assumptions to verify early. They are not
established facts.*
