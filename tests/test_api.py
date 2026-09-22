import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.main import app


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value:
        yield value


@pytest.mark.asyncio
async def test_health_and_snapshot_contract(client: AsyncClient) -> None:
    assert (await client.get("/api/health")).json()["schema_version"] == "1.0"
    snapshot = await client.get("/api/snapshot")
    assert snapshot.status_code == 200
    body = snapshot.json()
    assert body["vehicle"]["vehicle_id"] == "AMB-01"
    assert len(body["routes"]) == 2


@pytest.mark.asyncio
async def test_accident_causes_perception_reroute(client: AsyncClient) -> None:
    await client.post("/api/reset")
    response = await client.patch("/api/controls", json={"accident": True})
    assert response.status_code == 200
    body = (await client.get("/api/snapshot")).json()
    selected = next(route for route in body["routes"] if route["selected"])
    assert selected["route_id"] == "route-b"
    assert body["roads"][1]["blockage"] is True


@pytest.mark.asyncio
async def test_results_replay_and_adapter_endpoints(client: AsyncClient) -> None:
    results = await client.get("/api/results")
    assert results.status_code == 200
    assert results.json()["total_runs"] >= 180
    replay = await client.get("/api/replays/ghost?seed=3")
    assert replay.status_code == 200
    assert {item["baseline"] for item in replay.json()["metrics"]} == {"B0", "B5"}
    assert replay.json()["demonstration_only"] is True
    roads = await client.get("/api/roads")
    assert roads.status_code == 200
    assert len(roads.json()["features"]) > 500
    adapters = (await client.get("/api/adapters")).json()
    assert adapters["fast"]["available"] is True
