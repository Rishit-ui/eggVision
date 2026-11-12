import pytest


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded", "error"}
    assert body["database"]["status"] in {"ok", "error"}
    assert body["redis"]["status"] in {"ok", "error"}
    assert body["storage"]["status"] in {"ok", "degraded", "error"}
    assert body["model_service"]["status"] == "not_ready"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
