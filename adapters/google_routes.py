"""Google Routes v2 runtime adapter; responses are never retained for training."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from schema import GeoPoint

from .base import AdapterUnavailable


@dataclass(frozen=True, slots=True)
class GoogleRoute:
    duration_s: float
    static_duration_s: float
    distance_m: int
    encoded_polyline: str
    speed_intervals: list[dict[str, int | str]]

    @property
    def congestion_ratio(self) -> float:
        return self.duration_s / max(1, self.static_duration_s)


def _duration_seconds(value: str) -> float:
    if not value.endswith("s"):
        raise ValueError(f"unexpected Google duration {value!r}")
    return float(value[:-1])


class GoogleRoutesAdapter:
    endpoint = "https://routes.googleapis.com/directions/v2:computeRoutes"

    def __init__(self, api_key: str | None = None, timeout_s: float = 10) -> None:
        self.api_key = api_key or os.getenv("GOOGLE_ROUTES_API_KEY")
        self.timeout_s = timeout_s

    def compute(self, origin: GeoPoint, destination: GeoPoint) -> list[GoogleRoute]:
        if not self.api_key:
            raise AdapterUnavailable("GOOGLE_ROUTES_API_KEY is not configured")
        body = {
            "origin": {"location": {"latLng": {"latitude": origin.lat, "longitude": origin.lon}}},
            "destination": {
                "location": {
                    "latLng": {"latitude": destination.lat, "longitude": destination.lon}
                }
            },
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE",
            "computeAlternativeRoutes": True,
            "extraComputations": ["TRAFFIC_ON_POLYLINE"],
            "languageCode": "en-IN",
            "units": "METRIC",
        }
        field_mask = (
            "routes.duration,routes.staticDuration,routes.distanceMeters,"
            "routes.polyline.encodedPolyline,routes.travelAdvisory.speedReadingIntervals"
        )
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body).encode(),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": field_mask,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:  # noqa: S310
                payload = json.load(response)
        except urllib.error.URLError as error:
            raise AdapterUnavailable(f"Google Routes request failed: {error}") from error
        return [
            GoogleRoute(
                duration_s=_duration_seconds(route["duration"]),
                static_duration_s=_duration_seconds(route["staticDuration"]),
                distance_m=route["distanceMeters"],
                encoded_polyline=route["polyline"]["encodedPolyline"],
                speed_intervals=route.get("travelAdvisory", {}).get("speedReadingIntervals", []),
            )
            for route in payload.get("routes", [])
        ]
