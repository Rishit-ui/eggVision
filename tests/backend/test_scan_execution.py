"""Execution-path tests for scan worker, storage, persistence and responses."""

import asyncio
import io
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import cv2
import numpy as np
import pytest
from fastapi import HTTPException, Response, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request

from app.routers import scan as scan_router
from app.schemas.scan import ScanCreate
from app.services.cv_service import CVService
from app.services.scan_service import ScanService


def jpeg_bytes() -> bytes:
    image = np.full((320, 240, 3), (15, 15, 20), dtype=np.uint8)
    cv2.ellipse(image, (120, 160), (55, 85), 0, 0, 360, (40, 140, 230), -1)
    ok, buffer = cv2.imencode(".jpg", image)
    assert ok
    return buffer.tobytes()


def request_with_id(request_id: str = "scan-test-123") -> Request:
    return Request({"type": "http", "method": "POST", "path": "/api/v1/scan", "headers": [(b"x-request-id", request_id.encode())]})


def persisted_scan() -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(), egg_id=None, batch_id=None, original_image_url="/uploads/original.jpg",
        processed_image_url=None, image_quality="ACCEPTABLE", image_quality_score=None,
        image_quality_warnings=[], capture_date=now, created_at=now,
    )


def test_successful_scan_with_mocked_pipeline_and_response_serialization(monkeypatch):
    monkeypatch.setattr(scan_router.image_service, "validate_image", lambda _: (True, "Valid image"))
    monkeypatch.setattr(scan_router.image_service, "canonical_upload_details", lambda _: ("image/jpeg", ".jpg"))
    scan = persisted_scan()
    monkeypatch.setattr(scan_router.storage_service, "upload_image", AsyncMock(return_value="/uploads/original.jpg"))
    monkeypatch.setattr(scan_router.cv_service, "process_scan_image", AsyncMock(return_value={
        "image_quality": "ACCEPTABLE", "quality_score": None, "warnings": [], "retake_recommended": False,
        "recommendation": None, "analysis": {"status": "UNCERTAIN"}, "candidate_geometry": None,
    }))
    monkeypatch.setattr(scan_router.scan_service, "create_scan", AsyncMock(return_value=scan))
    image = UploadFile(filename="capture.jpg", file=io.BytesIO(jpeg_bytes()))

    with patch.object(scan_router.logger, "info") as info:
        result = asyncio.run(scan_router.create_scan(
            request_with_id(), Response(), image, json.dumps({}), SimpleNamespace(),
        ))

    assert result.id == scan.id
    assert result.image_quality_score is None
    assert any("scan_stage=response_serialization_completed request_id=%s" in call.args[0] for call in info.call_args_list)


def test_slow_pipeline_runs_without_blocking_event_loop():
    service = CVService()

    class SlowPipeline:
        def process(self, image):
            time.sleep(0.15)
            return SimpleNamespace(normalization=None, to_dict=lambda: {"analysis": {}, "warnings": []})

    service.pipeline = SlowPipeline()
    observed = []

    async def heartbeat():
        await asyncio.sleep(0.02)
        observed.append("event-loop-ran")

    async def run_concurrently():
        await asyncio.gather(service.process_scan_image(jpeg_bytes(), "capture.jpg", "worker-test"), heartbeat())

    asyncio.run(run_concurrently())
    assert observed == ["event-loop-ran"]


def test_cv_exception_is_logged_and_returned_as_safe_502(monkeypatch):
    monkeypatch.setattr(scan_router.image_service, "validate_image", lambda _: (True, "Valid image"))
    monkeypatch.setattr(scan_router.image_service, "canonical_upload_details", lambda _: ("image/jpeg", ".jpg"))
    monkeypatch.setattr(scan_router.storage_service, "upload_image", AsyncMock(return_value="/uploads/original.jpg"))
    monkeypatch.setattr(scan_router.cv_service, "process_scan_image", AsyncMock(side_effect=RuntimeError("pipeline boom")))
    image = UploadFile(filename="capture.jpg", file=io.BytesIO(jpeg_bytes()))

    with patch.object(scan_router.logger, "exception") as exception_log, pytest.raises(HTTPException) as error:
        asyncio.run(scan_router.create_scan(request_with_id(), Response(), image, json.dumps({}), SimpleNamespace()))

    assert error.value.status_code == 502
    assert any("category=cv_processing" in call.args[0] for call in exception_log.call_args_list)


def test_original_storage_failure_is_logged_and_returned_as_safe_502(monkeypatch):
    monkeypatch.setattr(scan_router.image_service, "validate_image", lambda _: (True, "Valid image"))
    monkeypatch.setattr(scan_router.image_service, "canonical_upload_details", lambda _: ("image/jpeg", ".jpg"))
    monkeypatch.setattr(scan_router.storage_service, "upload_image", AsyncMock(side_effect=OSError("storage unavailable")))
    image = UploadFile(filename="capture.jpg", file=io.BytesIO(jpeg_bytes()))

    with patch.object(scan_router.logger, "exception") as exception_log, pytest.raises(HTTPException) as error:
        asyncio.run(scan_router.create_scan(request_with_id(), Response(), image, json.dumps({}), SimpleNamespace()))

    assert error.value.status_code == 502
    assert any("category=original_image_storage" in call.args[0] for call in exception_log.call_args_list)


def test_database_failure_rolls_back_without_partial_scan_record():
    class FailingSession:
        def __init__(self):
            self.added = []
            self.rolled_back = False

        def add(self, item):
            self.added.append(item)

        async def flush(self):
            raise SQLAlchemyError("database unavailable")

        async def rollback(self):
            self.rolled_back = True

    db = FailingSession()
    with pytest.raises(SQLAlchemyError):
        asyncio.run(ScanService().create_scan(db, "/uploads/original.jpg", ScanCreate()))
    assert db.rolled_back is True
    assert len(db.added) == 1
