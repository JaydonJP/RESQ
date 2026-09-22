# Thousand Lights SUMO network

This SUMO network preview is **not** the source of the current web demonstration.
The review demo routes over the checked-in `roads.json` OSM graph. SUMO currently
generates a network and random background trips but does not run the ambulance
decision loop. Do not use the web replay as evidence of SUMO performance.

The generated network is intentionally not committed because OpenStreetMap data
changes and the exact junction corrections must remain reviewable. After installing
SUMO and setting `SUMO_HOME`, run:

```powershell
uv run python sim/chennai/build_network.py
sumo-gui -c sim/chennai/chennai.sumocfg
```

The checked-in bounding box is the project starting point around Apollo Hospitals,
Greams Road. Before collecting final results, inspect every signal, one-way, turn
restriction, and the Gemini flyover in `sumo-gui`; store corrections as plain-XML
patches rather than editing the generated `.net.xml` directly.

Generated files are placed under `sim/chennai/generated/` and ignored by Git.
