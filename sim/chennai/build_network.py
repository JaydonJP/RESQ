"""Download the study-area OSM extract and build repeatable SUMO inputs."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

BOUNDING_BOX = "80.2370,13.0520,80.2600,13.0700"  # west,south,east,north
HERE = Path(__file__).resolve().parent
GENERATED = HERE / "generated"


def _run(command: list[str]) -> None:
    print(" ".join(command))
    subprocess.run(command, check=True)  # noqa: S603


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bbox", default=BOUNDING_BOX)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--period", type=float, default=1.5)
    args = parser.parse_args()

    sumo_home_value = os.getenv("SUMO_HOME")
    if not sumo_home_value:
        raise SystemExit("SUMO_HOME must point to the installed SUMO directory")
    sumo_home = Path(sumo_home_value).resolve()
    osm_get = sumo_home / "tools" / "osmGet.py"
    random_trips = sumo_home / "tools" / "randomTrips.py"
    netconvert = shutil.which("netconvert")
    polyconvert = shutil.which("polyconvert")
    if not osm_get.exists() or not random_trips.exists() or not netconvert or not polyconvert:
        raise SystemExit("SUMO tools, netconvert, or polyconvert are missing from the installation/PATH")

    GENERATED.mkdir(parents=True, exist_ok=True)
    _run(
        [
            sys.executable,
            str(osm_get),
            "--bbox",
            args.bbox,
            "--prefix",
            "thousand_lights",
            "-d",
            str(GENERATED),
        ]
    )
    osm_files = sorted(GENERATED.glob("thousand_lights*.osm.xml"))
    if not osm_files:
        raise SystemExit("osmGet completed without producing an .osm.xml file")
    network = GENERATED / "thousand_lights.net.xml"
    _run(
        [
            netconvert,
            "--osm-files",
            ",".join(str(path) for path in osm_files),
            "--output-file",
            str(network),
            "--geometry.remove",
            "--roundabouts.guess",
            "--ramps.guess",
            "--junctions.join",
            "--tls.guess",
            "--tls.guess-signals",
            "--tls.discard-simple",
            "--tls.join",
            "--tls.cycle.time",
            "120",
            "--tls.yellow.time",
            "3",
            "--tls.allred.time",
            "2",
        ]
    )
    _run(
        [
            sys.executable,
            str(random_trips),
            "-n",
            str(network),
            "-r",
            str(GENERATED / "background.rou.xml"),
            "--period",
            str(args.period),
            "--seed",
            str(args.seed),
            "--validate",
            "--vehicle-class",
            "passenger",
            "--trip-attributes",
            'departLane="best" departSpeed="max"',
        ]
    )
    _run(
        [
            polyconvert,
            "--net-file",
            str(network),
            "--osm-files",
            ",".join(str(path) for path in osm_files),
            "--type-file",
            str(HERE / "landscape.typ.xml"),
            "--osm.keep-full-type",
            "--output-file",
            str(GENERATED / "landscape.poly.xml"),
        ]
    )
    _run(
        [
            sys.executable,
            str(HERE / "build_ambulance_route.py"),
            "--net",
            str(network),
        ]
    )
    print(f"Network ready: {network}")


if __name__ == "__main__":
    main()
