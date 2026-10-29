"""Integration tests for CV pipeline via FastAPI endpoints."""

import io
import json
import cv2
import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.database import get_db


def make_test_egg_image_bytes() -> bytes:
    """Generate JPEG bytes of an intact candled egg."""
    img = np.full((320, 240, 3), (15, 15, 20), dtype=np.uint8)
    cv2.ellipse(img, (120, 160), (55, 85), 0, 0, 360, (40, 140, 240), -1)
    cv2.ellipse(img, (120, 170), (35, 55), 0, 0, 360, (60, 180, 255), -1)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


class MockAsyncSession:
    """Mock session for testing endpoint without a live Postgres instance."""
    def __init__(self):
        self.added = []

    def add(self, obj):
        import uuid
        from datetime import datetime, timezone
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = uuid.uuid4()
        if not hasattr(obj, "created_at") or obj.created_at is None:
            obj.created_at = datetime.now(timezone.utc)
        if not hasattr(obj, "capture_date") or obj.capture_date is None:
            obj.capture_date = datetime.now(timezone.utc)
        self.added.append(obj)

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass


async def override_get_db():
    yield MockAsyncSession()


@pytest.mark.asyncio
async def test_scan_with_cv_pipeline():
    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            img_bytes = make_test_egg_image_bytes()
            metadata_str = json.dumps({"temperature": 24.5, "humidity": 65.0})

            files = {
                "image": ("test_egg.jpg", img_bytes, "image/jpeg"),
            }
            data = {
                "metadata": metadata_str,
            }

            response = await client.post("/api/v1/scan", files=files, data=data)
            assert response.status_code == 201

            body = response.json()
            assert "id" in body
            assert "original_image_url" in body
            assert body["original_image_url"].endswith(".jpg")
            assert "processed_image_url" in body
            assert body["processed_image_url"] is not None
            assert body["image_quality"] in ["GOOD", "ACCEPTABLE"]
            assert body["image_quality_score"] > 0.60
            assert isinstance(body["image_quality_warnings"], list)
            assert body["retake_recommended"] is False
            assert body["analysis"]["status"] == "UNCERTAIN"
            assert body["analysis"]["model"]["validated_egg_detector"] is False
            assert body["egg_geometry"] is None
            assert body["candidate_contour_geometry"] is not None
    finally:
        app.dependency_overrides.clear()
