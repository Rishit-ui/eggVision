import pytest

@pytest.mark.asyncio
async def test_scan_creates_record(client):
    response = await client.post("/api/v1/scan")
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_predict_requires_scan_id(client):
    response = await client.post("/api/v1/predict")
    assert response.status_code == 422
