import pytest

@pytest.mark.asyncio
async def test_scan_creates_record(client):
    response = await client.post("/api/v1/scan")
    assert response.status_code in [200, 201]

@pytest.mark.asyncio
async def test_predict_returns_not_ready(client):
    response = await client.post("/api/v1/predict")
    assert response.status_code == 200
    assert response.json().get("status") == "model_not_ready"
