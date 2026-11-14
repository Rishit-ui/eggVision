import pytest
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_get_model_info():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/model/info")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["is_ready"], bool)
        if data["is_ready"]:
            assert data["model_type"] in {"yolo_detection", "yolov8n_onnx_detection", "placeholder"}
            assert data["state"] == "MODEL_READY"
        else:
            assert data["model_type"] == "placeholder"
            assert "No trained model" in data["description"]
