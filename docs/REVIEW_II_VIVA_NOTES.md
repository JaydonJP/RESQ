# ResQ Review II: Viva and Technical Notes

These notes are for explaining the current repository honestly. The current
system is a working fast-mode vertical slice. It is not yet a finished
SUMO-CARLA deployment or a trained production ML system.

## 1. The project in one minute

ResQ is a predictive emergency-vehicle routing and traffic-signal
preemption system for an ambulance travelling through Thousand Lights,
Chennai, to Apollo Hospitals on Greams Road.

The central problem is that city-wide traffic information is useful but often
late. A recent accident may still look clear in the macro traffic feed. The
ambulance's camera and LiDAR can see a blockage a few seconds before the
macro system learns about it. ResQ combines both time scales:

1. Macro traffic data and forecasts describe roads several minutes ahead.
2. Onboard perception describes the next roughly 100-150 metres.
3. Fusion produces a confidence-aware travel-time estimate for each road.
4. Time-dependent routing selects the route to the hospital.
5. A corridor controller requests green signals only when needed and performs
   safe signal transitions.
6. The browser shows the live route, signal state, confidence, decisions,
   replay, driver view, and experiment results.

The centrepiece demo is the hidden accident. Initially macro traffic selects
Route A. The onboard sensor sees stopped vehicles across two lanes, fusion
marks the road near-closed, routing switches to Route B, and the corridor
controller prepares the next intersections.

## 2. What is actually complete now

The current fast-mode prototype includes:

- A deterministic demo simulation with Route A and Route B.
- Controls for hidden accident, macro-feed availability, camera availability,
  and probe adoption.
- Version-one Pydantic contracts shared by simulation, decisions, API, and UI.
- Crowd-GPS probe generation with adoption, noise, dropout, and lag.
- Historical-average and graph-smoothed explainable forecast baselines.
- Vehicle tracking data structures, blockage detection, short-horizon track
  prediction, and deterministic LiDAR clustering.
- Inverse-variance fusion and a high-confidence blockage override.
- Time-dependent shortest-path routing and route hysteresis.
- A deterministic signal state machine with request, pre-clear, safe
  transition, emergency service, passed, recovery, and normal phases.
- Seeded B0-B5 experiment generation, SQLite persistence, p95 and 95% CI
  summaries, and synchronized B0/B1/B5 replay data.
- FastAPI REST endpoints and a 5 Hz WebSocket snapshot stream.
- React/TypeScript/MapLibre Live, Replay, Cab, and Results workspaces.
- Automated tests, linting, and a successful frontend production build.

The current stored results contain 180 fast-mode runs across six scenarios and
six baselines. The Results page reports approximately 28.9% mean B5
improvement over B0, 95.8% green-on-arrival for B5, and zero conflicting-green
violations. These are fast-mode software results, not claims about real
Chennai traffic.

## 3. What must not be claimed as complete

The following are interfaces or planned paths, not completed validation:

- SUMO/TraCI is implemented as an optional adapter, but it is unavailable on
  the current machine unless SUMO and TraCI are installed and configured.
- CARLA sensor code is present, but a running CARLA server and the CARLA Python
  API are still required.
- Google Routes code is present, but it requires a runtime API key and has not
  been used to build training data.
- The current forecasting code is explainable baseline logic, not a trained
  graph neural network.
- The current perception pipeline consumes tracked objects and point clouds;
  it does not yet train YOLO on IDD or Chennai video.
- The fast experiment runner is a calibrated mesoscopic model. It is valuable
  for integration testing and repeatable comparisons, but it is not a
  replacement for a validated transport simulator.
- Actual personal contribution cannot be proved by the repository alone. Each
  member must understand and make a small, reviewable contribution before the
  viva.

## 4. System pipeline to memorise

```text
Macro probes / forecast ─┐
                         ├─> observation contracts ─> fusion ─> routing
Camera / LiDAR ──────────┘                                  │
                                                           v
                                      corridor safety controller
                                                           │
                                                           v
                                      signals + recorder + WebSocket + React
```

The important design rule is separation of concerns. Sensor-specific objects
should not leak into routing or the browser. Modules communicate through
shared contracts such as `RoadObservation`, `RoadEstimate`, `RouteOption`,
`PriorityRequest`, and `SignalState`.

## 5. Member 1: Simulation, Signals, and Experiments

### Short introduction to say

> I am responsible for the traffic and signal side of ResQ. My area
> models the road environment, produces repeatable traffic observations,
> controls the emergency corridor, and measures the system consistently across
> the B0-B5 baselines. The current implementation uses a deterministic
> fast-mode simulator so the complete workflow can be demonstrated without
> external binaries. The next step is to connect the same interfaces to SUMO.

### Work completed

#### Fast-mode simulation

`sim/demo.py` creates a compact vertical slice of the Chennai scenario. It
contains two candidate routes:

- Route A: Greams Road, initially fastest according to macro traffic.
- Route B: Haddows Road, the alternative route.

The simulation exposes controls for:

- `accident`: creates a hidden blockage on Route A.
- `macro_feed`: simulates fresh or stale macro traffic.
- `camera`: enables or disables onboard perception.
- `adoption_percent`: changes probe adoption.

When the accident and camera are enabled, road A2 receives a high-confidence
perception blockage. Route A becomes effectively near-closed and the route
decision changes to Route B.

#### Crowd-GPS probes

The probe generator does not pretend every phone equals one vehicle. It:

- Samples vehicles according to a configured adoption percentage.
- Adds GPS position noise.
- Adds speed noise.
- Simulates dropout.
- Simulates upload lag.
- Filters pedestrian-like and implausible speeds.
- Deduplicates samples by vehicle.
- Uses a robust median/MAD-style outlier filter.
- Estimates total vehicles by dividing observed samples by adoption rate.

The reason for using probes is that phones are imperfect observations. A phone
may belong to a passenger, several phones may be in one car, and pedestrians
must not be counted as vehicles. Speed is usually more useful than raw phone
count, so the system estimates road speed and treats vehicle count as an
approximation.

#### Signal corridor state machine

The controller deliberately does not let an ML model directly change a signal.
The transition sequence is deterministic:

```text
NORMAL -> REQUEST_VALID -> PRE_CLEAR -> SAFE_TRANSITION
       -> EV_SERVICE -> EV_PASSED -> RECOVERY -> NORMAL
```

The controller respects minimum green, amber, all-red, maximum preemption, and
recovery timings. The all-red phase is important because it clears conflicting
traffic before the ambulance approach receives service. The current state
object explicitly reports `conflicting_green=False`.

#### Experiment runner

The B0-B5 policies are incremental:

- B0: no traffic awareness, no preemption.
- B1: macro traffic-aware routing.
- B2: B1 plus fixed-distance preemption.
- B3: fused routing plus fixed-distance preemption.
- B4: fused routing plus just-in-time preemption.
- B5: B4 plus queue-debt recovery.

Every run receives a seed. The same seed and configuration produce the same
metrics apart from the generated run identifier. This makes comparisons fair:
the baseline changes, but demand noise, incident conditions, and signal
conditions are sampled in a repeatable way.

### Future work

1. Install and validate SUMO and TraCI.
2. Import the Thousand Lights map and manually verify roads, junctions,
   signal phases, turn restrictions, and emergency approaches.
3. Calibrate demand, vehicle classes, two-wheelers, auto-rickshaws, and
   emergency-vehicle behavior.
4. Connect SUMO traffic-light state and vehicle positions to the shared schema.
5. Implement realistic signal requests through TraCI.
6. Add feed-loss, stale-feed, night/rain, saturated, and two-ambulance cases.
7. Run at least 20 seeds per baseline/scenario/adoption cell.
8. Report confidence intervals, p95 travel time, green-on-arrival rate,
   cross-traffic delay, recovery time, and safety violations.

### Questions Member 1 may be asked

#### Why use a simulator?

> It gives us repeatable controlled experiments. We can inject the same
> accident and demand conditions into every baseline. The fast mode allows the
> software architecture and research logic to be tested even when SUMO or
> CARLA is not installed. For final transport claims, we still need the
> manually verified SUMO network and more seeds.

#### Why is reproducibility important?

> Without fixed seeds, a B0 run and a B5 run could receive different traffic
> conditions and the comparison would be unfair. We store the seed, scenario,
> baseline, and all derived metrics so a result can be repeated and traced.

#### Why not switch the signal immediately?

> Immediate switching can create conflicting greens and unsafe crossings. The
> controller first validates the request, clears the current movement, passes
> through amber and all-red, then gives the ambulance service. Safety is a
> deterministic rule, not a prediction.

#### What is queue-debt recovery?

> Preemption delays cross traffic. After the ambulance passes, the controller
> gives recovery service to approaches that waited. B5 models this as a lower
> cross-traffic delay and shorter recovery time than fixed preemption.

#### What does 5 Hz mean?

> The backend publishes a live snapshot approximately every 0.2 seconds over
> WebSocket. It is suitable for the demo control room. It is not the same as
> claiming that every physical sensor or signal controller operates at 5 Hz.

## 6. Member 2: Forecasting, Fusion, Routing, and Backend

### Short introduction to say

> I am responsible for turning observations into decisions. My area defines
> the shared data contracts, estimates future road conditions, fuses macro and
> onboard evidence, selects routes with hysteresis, and exposes the results
> through the FastAPI and WebSocket backend. The key contribution is that the
> system uses macro information for distant roads and fresh perception for the
> road immediately ahead.

### Work completed

#### Shared contracts

The `schema` package uses strict Pydantic models. Important contracts include:

- `VehicleState`: ambulance identity, position, speed, heading, route, progress.
- `RoadObservation`: source, travel time, uncertainty, confidence, age, distance,
  and blockage.
- `RoadEstimate`: the fused travel-time result and explanation.
- `RouteOption`: route geometry, ETA, selection state, and reason.
- `PriorityRequest`: intersection, approach, ETA, queue, confidence, expiry.
- `SignalState`: signal phase, active approach, timer, and safety flag.
- `RunMetrics`: travel time, stops, route switches, green rate, cross delay,
  recovery, reaction time, regret, and conflicting-green violations.

Strict contracts prevent accidental extra fields and keep Python modules and the
browser synchronized.

#### Forecasting baselines

The current forecasting code contains two explainable baselines:

1. `HistoricalAverageForecaster` groups speed records into 15-minute
   minute-of-week buckets and predicts the mean speed for the target horizon.
2. `SpatialTemporalForecaster` uses recent speed, recent trend, neighboring-road
   speed, and a persistence factor to produce 5-, 15-, and 30-minute forecasts.

These are intentionally simple. They establish a baseline and give the system
an uncertainty estimate before GPU-based graph models are introduced.

#### Confidence-aware fusion

Fusion receives macro and perception observations for the same road.

For ordinary observations it uses inverse-variance weighting:

```text
weight_i = 1 / standard_deviation_i^2
estimate = sum(weight_i * travel_time_i) / sum(weight_i)
```

Lower uncertainty gives a larger weight. Macro uncertainty is increased as the
observation becomes older. Perception uncertainty is increased with distance
from the ambulance and reduced confidence.

There is also a safety-oriented override: if perception reports a blockage with
confidence at least 0.8, the road is treated as near-closed with a travel time
of 3600 seconds. This prevents a stale macro estimate from averaging away a
high-confidence immediate hazard.

#### Routing and hysteresis

The routing core is a graph search similar to Dijkstra's algorithm. The edge
cost can depend on the time at which the ambulance enters the edge, so it is
time-dependent rather than simply distance-based.

The route policy switches only when both conditions hold:

- The candidate saves at least 10 seconds.
- The candidate saves at least 5 percent.

This prevents route flip-flopping due to small noisy differences. It also
avoids repeatedly cancelling and recreating signal reservations.

#### FastAPI backend

The backend provides:

- `/api/health`: process and schema health.
- `/api/adapters`: availability of fast, SUMO, CARLA, and Google modes.
- `/api/snapshot`: current normalized network state.
- `/api/controls`: accident, feed, camera, and adoption controls.
- `/api/reset`: reset the live scenario.
- `/api/experiments/run`: execute and persist a matrix.
- `/api/results`: aggregate recorded results.
- `/api/replays` and `/api/replays/ghost`: replay catalogue and synchronized run.
- `/ws/live`: live snapshots at approximately 5 Hz.

The API returns structured schema objects rather than UI-specific data. This
allows the browser to be replaced without changing decision logic.

### Future work

1. Train real forecasting models on PEMS-BAY/METR-LA and simulated Chennai
   history, then compare them with the explainable baselines.
2. Report MAE, RMSE, and MAPE separately for 5-, 15-, and 30-minute horizons.
3. Calibrate confidence and uncertainty with held-out data.
4. Connect SUMO snapshots to the same schema without changing routing code.
5. Complete Google Routes runtime mode while keeping API keys server-side and
   never using Google responses as training history.
6. Add route-regret comparison against an all-knowing oracle.
7. Add stronger API validation, logging, deployment configuration, and Docker
   health checks.
8. Run fusion-off, forecast-only, perception-only, and adoption ablations.

### Questions Member 2 may be asked

#### Why combine macro traffic and onboard perception?

> They cover different time and distance horizons. Macro data can describe
> distant roads but may be minutes old. Onboard perception is fresh and useful
> nearby, but cannot see kilometres ahead. Fusion combines the strengths of
> both rather than treating one as universally correct.

#### Why inverse variance?

> It is a transparent probabilistic weighting rule. An observation with smaller
> expected error receives more influence. It is easy to test and explain. A
> learned fusion model could be evaluated later, but the baseline must remain
> interpretable.

#### Why does perception override instead of just receive a larger weight?

> A real blockage is not merely a slightly slower travel time. If we average a
> stale macro time of 40 seconds with a perception time of 210 seconds, the
> result might still look passable. A high-confidence two-lane blockage should
> be treated as a near-closed road, so the explicit override is safer.

#### What is route hysteresis?

> Hysteresis is a threshold that prevents switching back and forth when route
> estimates are nearly equal. ResQ requires both a 10-second and a 5%
> improvement before changing route.

#### Why FastAPI and WebSockets?

> FastAPI provides typed REST endpoints and good Python integration with the
> simulation and research modules. WebSockets provide continuous live snapshots
> without repeated browser polling. The current demo stream is 5 Hz.

#### Is the current forecast an AI model?

> It is an explainable baseline, not the final graph neural network. The
> architecture isolates forecasting so a trained model can replace the baseline
> while the fusion, routing, API, and UI contracts remain stable.

## 7. Member 3: Perception, CARLA, Web, and Demonstration

### Short introduction to say

> I am responsible for the ambulance-side evidence and the examiner-facing
> application. My area converts tracked objects and LiDAR points into queue and
> blockage observations, provides the CARLA sensor adapter, and presents the
> live, replay, cab, and results views. The UI is not just decoration: it makes
> the system's decisions, confidence, signal state, and experimental evidence
> visible.

### Work completed

#### Perception pipeline

The current sensor-agnostic pipeline defines a `TrackedObject` with:

- Track ID.
- Object class.
- Lane ID.
- Distance ahead.
- Lateral position.
- Speed.
- Time stopped.
- Detector confidence.

The blockage detector marks a road blocked when at least three tracked objects
have been stopped for at least three seconds across at least two lanes. It
produces a `RoadObservation` with an estimated travel time, standard deviation,
confidence, queue tail, and blockage flag.

Short-horizon prediction uses a simple constant-velocity assumption:

```text
future distance = current distance - speed * horizon
```

It also reports a gap-opening hint when speed and lateral movement suggest a
vehicle may be making room.

The LiDAR stage currently uses deterministic Euclidean clustering over filtered
ground-plane points. It groups nearby points into objects and ignores clusters
below a minimum point count.

#### CARLA sensor adapter

The CARLA adapter is an optional integration layer. When CARLA is installed, it:

- Connects to a CARLA server.
- Enables synchronous mode at 20 Hz.
- Attaches a 1280x720 RGB camera.
- Attaches a 32-channel LiDAR with 70 metre range.
- Buffers camera and LiDAR frames.
- Cleans up actors and restores asynchronous settings on close.

The adapter is present, but it is not currently available without the CARLA
Python API and a running server.

#### React application

The browser has four workspaces:

- Live: map, route options, ETA, confidence, controls, signals, and decision log.
- Replay: synchronized B0/B1/B5 ghost race with play/pause/scrub.
- Cab: next manoeuvre, route, signal pre-clear status, speed, ETA, and confidence.
- Results: B0-B5 travel-time chart, green-on-arrival, stops, cross-traffic delay,
  p95 trip time, and confidence interval.

The frontend receives the live snapshot through WebSocket and sends control
changes through the REST API. The UI therefore exercises the same backend path
that an external client would use.

### Future work

1. Connect CARLA camera frames to a YOLO/ByteTrack detector.
2. Fine-tune and evaluate on IDD plus a labelled Chennai sample.
3. Add night and rain conditions and report degradation.
4. Align camera detections and LiDAR clusters in time and coordinates.
5. Produce real detection boxes and synchronized camera replay.
6. Add perception metrics: precision, recall, mAP, blockage false-positive rate,
   and detection latency.
7. Improve the Results page with forecast and perception metrics, scenario
   filters, adoption curves, and signal timelines.
8. Test tablet-sized layout, accessibility, reconnection behavior, and static
   deployment.
9. Prepare the final demo script and screenshots.

### Questions Member 3 may be asked

#### Why use both camera and LiDAR?

> Camera provides semantic information such as vehicle class and lane context.
> LiDAR provides geometric distance and clustering that is less dependent on
> lighting. Their combination is useful for detecting stopped queues and
> estimating how far the queue extends.

#### Why require stopped vehicles in two lanes?

> A single stopped vehicle may be a normal stop, parking event, or detector
> error. Multiple stopped vehicles across two lanes are stronger evidence that
> the road is obstructed. The threshold is a configurable baseline and must be
> calibrated with real validation data.

#### Why is the current perception not called a trained detector?

> The current code defines the downstream perception contract and deterministic
> blockage logic. It accepts tracked objects rather than training YOLO inside
> this repository. The next phase is to connect CARLA/YOLO/ByteTrack and measure
> performance on IDD and Chennai data.

#### What does the Results page prove?

> It proves that the experiment pipeline can persist, aggregate, and display
> comparable seeded runs. It does not by itself prove real-world traffic
> performance. The results must be labelled as fast-mode simulation evidence.

#### Why have a Cab page?

> It demonstrates the operational interface for an ambulance driver: route,
> next signal, ETA, speed, confidence, and a gap-opening hint. It also shows
> how the research outputs could become an actionable interface.

## 8. Cross-member questions

### What is the main innovation?

> The innovation is the combination of forecasted macro traffic, fresh onboard
> perception, confidence-aware fusion, time-dependent rerouting, and
> just-in-time safe signal coordination. A normal navigation app can provide
> crowd traffic routing, but it does not have the ambulance's immediate sensor
> view or control a safe emergency corridor.

### Why not just use Google Maps?

> Google-style routing is represented by B1 as a baseline. ResQ adds
> local perception, accident detection, route hysteresis, signal preemption,
> and queue-debt recovery. Google data is optional runtime input and is not used
> as training history.

### What happens if the camera fails?

> The health state marks perception as offline and confidence decreases. The
> macro source can still provide a route, but it may miss a fresh hidden
> accident. This is intentionally represented as a degraded-camera scenario and
> must be measured rather than hidden.

### What happens if the macro feed fails?

> Macro age increases and the system relies more on available perception. If
> both macro and camera are unavailable, the fast demo retains a route but
> confidence is lower. A production system should expose a degraded mode and
> apply operational safety policies rather than silently pretending confidence.

### How do you prevent unsafe signal behavior?

> Signal transitions are owned by the deterministic corridor state machine.
> Prediction can request priority, but it cannot skip minimum green, amber,
> all-red, expiration, or recovery. Safety is tested separately from route
> quality, and the recorded conflicting-green metric must remain zero.

### How is fairness maintained between baselines?

> All baselines use the same scenario, seed, demand sampling, and signal
> conditions. Only the documented capability changes: traffic awareness,
> perception, preemption type, or recovery. Results are persisted with the seed
> and baseline identifier.

### What are the biggest limitations?

> The present evidence is fast-mode simulation evidence. External SUMO and
> CARLA validation, trained perception, trained forecasting, real Chennai data,
> and larger seed counts remain. We will not present the current percentages as
> real-road guarantees.

## 9. Useful numbers to remember

- Live stream: approximately 5 Hz.
- Hidden accident perception confidence in the demo: 0.93.
- High-confidence blockage threshold: 0.80.
- Near-closed travel time used by the fusion override: 3600 seconds.
- Route switch threshold: at least 10 seconds and 5% improvement.
- Signal sensor configuration target: 20 Hz CARLA synchronous mode.
- CARLA camera target: 1280x720 RGB.
- CARLA LiDAR target: 32 channels and 70 metre range.
- Current stored results: 180 runs, 6 scenarios, 6 baselines.
- Current aggregate B5 improvement: approximately 28.9% versus B0.
- Current aggregate B5 green-on-arrival rate: approximately 95.8%.
- Current recorded conflicting-green violations: 0.
- Ghost replay seed 7: B0/B1 about 329.9 seconds, B5 about 164.9 seconds.

## 10. Immediate preparation before the review

Each member should do these things before claiming ownership:

1. Read their section and run the application.
2. Open the relevant source files and be able to point to the main function or
   class.
3. Make one small legitimate improvement in their area, add or update a test,
   and understand the resulting diff.
4. Prepare a one-minute explanation, a two-minute technical explanation, and a
   limitation statement.
5. Practice the cross-member questions so nobody gives contradictory answers.

The safest wording is “our current prototype implements...” for shared work and
“my assigned area is...” for the member's area. Do not say that a model was
trained, a CARLA demo was run, or a SUMO map was validated unless that work has
actually been completed before the review.

