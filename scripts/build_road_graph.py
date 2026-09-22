"""Download a small, reproducible OSM road extract for the Chennai demo.

The checked-in JSON is the runtime input; this script is only needed to refresh it.
Data: © OpenStreetMap contributors, ODbL (openstreetmap.org/copyright).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree

BBOX = (80.231, 13.051, 80.260, 13.071)
URL = "https://api.openstreetmap.org/api/0.6/map?bbox=" + ",".join(map(str, BBOX))
OUTPUT = Path(__file__).resolve().parents[1] / "sim" / "chennai" / "roads.json"
DRIVABLE = {
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
    "unclassified",
    "residential",
    "living_street",
    "service",
}


def main() -> None:
    request = Request(URL, headers={"User-Agent": "ResQ-College-Demo/0.1 (road graph research)"})
    with urlopen(request, timeout=45) as response:
        root = ElementTree.parse(response).getroot()
    nodes = {
        element.attrib["id"]: [float(element.attrib["lat"]), float(element.attrib["lon"])]
        for element in root.findall("node")
    }
    ways = []
    used_nodes = set()
    for element in root.findall("way"):
        tags = {tag.attrib["k"]: tag.attrib["v"] for tag in element.findall("tag")}
        if tags.get("highway") not in DRIVABLE:
            continue
        if tags.get("access") in {"no", "private"} or tags.get("motor_vehicle") in {
            "no",
            "private",
        }:
            continue
        if tags.get("vehicle") in {"no", "private"} or tags.get("service") in {
            "parking_aisle",
            "driveway",
        }:
            continue
        refs = [child.attrib["ref"] for child in element.findall("nd")]
        if len(refs) < 2 or not all(ref in nodes for ref in refs):
            continue
        ways.append(
            {
                "id": element.attrib["id"],
                "nodes": refs,
                "name": tags.get("name", "Unnamed road"),
                "highway": tags["highway"],
                "oneway": tags.get(
                    "oneway", "yes" if tags.get("junction") == "roundabout" else "no"
                ),
            }
        )
        used_nodes.update(refs)
    payload = {
        "source": URL,
        "licence": "OpenStreetMap contributors, ODbL 1.0",
        "downloaded_at": datetime.now(UTC).isoformat(),
        "bbox": BBOX,
        "nodes": {key: nodes[key] for key in sorted(used_nodes, key=int)},
        "ways": ways,
    }
    OUTPUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"Saved {len(ways)} drivable ways, {len(used_nodes)} nodes to {OUTPUT}")


if __name__ == "__main__":
    main()
