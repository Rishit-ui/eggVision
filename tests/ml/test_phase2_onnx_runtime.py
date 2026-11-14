"""test_phase2_onnx_runtime.py
Comprehensive automated test suite for EggVision Phase 2:
Model Artifact Management, ONNX Inference Runtime, Backend Integration, and End-to-End Predict Flow.

Covers:
1. ONNX export metadata, manifest, and equivalence verification report.
2. Preprocessing, letterboxing, tensor conversion, and NMS decoding.
3. OnnxDetectionEngine integrity checks, checksum mismatch rejection, missing file,
   corrupt file, ONNX Runtime unavailable fallback, and scientific honesty.
4. ModelLifecycleManager startup resolution, S3 download caching, and status telemetry.
5. Storage key extraction and /predict endpoint end-to-end integration.
"""

import hashlib
import json
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import cv2
import numpy as np
import pytest
from app.models.prediction import Prediction
from app.models.scan import Scan
from app.models.user import User
from app.routers.predict import extract_storage_key, predict_scan
from app.schemas.prediction import PredictRequest
from app.services.model_loader import ModelLifecycleManager
from app.services.prediction_service import prediction_service

from ml.inference.onnx_detection_engine import (
    OnnxDetectionEngine,
    get_onnx_inference_engine,
    letterbox_image,
)
from ml.inference.placeholder import PlaceholderEngine


class TestOnnxArtifactsAndProvenance:
    """Verify generated Phase 2 metadata artifacts exist and are cryptographically consistent."""

    def test_onnx_metadata_file_validity(self):
        meta_path = Path("ml/artifacts/detection/onnx_metadata.json")
        assert meta_path.exists(), "onnx_metadata.json must exist"
        data = json.loads(meta_path.read_text(encoding="utf-8"))

        assert data["format"] == "onnx"
        assert data["model_architecture"] == "yolov8n"
        assert data["input_resolution"] == [640, 640]
        assert "onnx_sha256" in data
        assert len(data["onnx_sha256"]) == 64
        assert data["onnx_size_bytes"] > 10_000_000
        assert data["graph_validation"]["ir_version"] is not None

    def test_manifest_file_provenance(self):
        manifest_path = Path("ml/artifacts/detection/manifest.json")
        assert manifest_path.exists(), "manifest.json must exist"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        assert manifest["manifest_version"] == "1.0.0"
        assert manifest["task"] == "detection"
        assert manifest["onnx_artifact"]["format"] == "onnx"
        assert manifest["onnx_artifact"]["opset"] == 17
        assert manifest["provenance"]["training_library"] == "ultralytics==8.4.212"
        assert manifest["provenance"]["dataset_source"] == "afshin-dini/Egg-Detection"

    def test_equivalence_report_passed(self):
        equiv_path = Path("ml/artifacts/detection/onnx_equivalence_report.json")
        assert equiv_path.exists(), "onnx_equivalence_report.json must exist"
        report = json.loads(equiv_path.read_text(encoding="utf-8"))

        assert report["status"] == "PASSED_EQUIVALENT"
        assert report["summary"]["total_images"] >= 8
        assert report["summary"]["count_matches"] == report["summary"]["total_images"]
        assert report["summary"]["mean_iou"] >= 0.90
        assert report["summary"]["mean_confidence_diff"] <= 0.03
        assert report["summary"]["speedup_factor"] > 1.0


class TestOnnxPreprocessingAndDecoding:
    """Test letterboxing, coordinate scaling, and Non-Maximum Suppression."""

    def test_letterbox_image_aspect_preservation(self):
        # Create non-square image: 300 x 600
        img = np.zeros((300, 600, 3), dtype=np.uint8)
        target = 640
        letterboxed, scale, (left, top) = letterbox_image(img, target_size=target)

        assert letterboxed.shape == (target, target, 3)
        assert scale == target / 600
        assert left == 0  # Width fills the target
        assert top > 0  # Vertical padding applied
        # Check border value is 114
        assert letterboxed[0, 0, 0] == 114

    def test_letterbox_grayscale_and_rgba(self):
        gray = np.zeros((400, 400), dtype=np.uint8)
        out_gray, scale_g, _ = letterbox_image(gray, target_size=640)
        assert out_gray.shape[:2] == (640, 640)

        rgba = np.zeros((200, 200, 4), dtype=np.uint8)
        out_rgba, scale_r, _ = letterbox_image(rgba, target_size=640)
        assert out_rgba.shape[:2] == (640, 640)

    def test_nms_suppression_logic(self):
        # Two highly overlapping boxes and one distinct box
        boxes = [[50.0, 50.0, 100.0, 100.0], [52.0, 51.0, 99.0, 101.0], [300.0, 300.0, 80.0, 80.0]]
        scores = [0.95, 0.90, 0.88]
        indices = cv2.dnn.NMSBoxes(boxes, scores, score_threshold=0.25, nms_threshold=0.50)
        flat = np.array(indices).flatten()
        assert len(flat) == 2  # The second overlapping box must be suppressed
        assert flat[0] == 0  # Highest score kept


class TestOnnxDetectionEngine:
    """Test OnnxDetectionEngine adapter integrity, fallback, and predictions."""

    def test_missing_weights_fallback(self, tmp_path: Path):
        engine = OnnxDetectionEngine(model_path=tmp_path / "missing.onnx")
        assert engine.is_ready() is False
        info = engine.get_model_info()
        assert info.is_ready is False
        assert "missing, corrupt, or rejected" in info.description

    def test_empty_weights_fallback(self, tmp_path: Path):
        empty_file = tmp_path / "empty.onnx"
        empty_file.touch()
        engine = OnnxDetectionEngine(model_path=empty_file)
        assert engine.is_ready() is False

    def test_checksum_mismatch_rejected(self, tmp_path: Path):
        fake_bytes = b"tampered_onnx_model_contents"
        fake_file = tmp_path / "model.onnx"
        fake_file.write_bytes(fake_bytes)

        meta_file = tmp_path / "manifest.json"
        meta_file.write_text(
            json.dumps({"onnx_artifact": {"sha256": "0000000000000000000000000000000000000000000000000000000000000000"}}),
            encoding="utf-8",
        )

        mock_ort = MagicMock()
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            engine = OnnxDetectionEngine(model_path=fake_file, metadata_path=meta_file)
            assert engine.is_ready() is False
            assert engine.session is None
            info = engine.get_model_info()
            assert info.is_ready is False

            # Factory function falls back to placeholder
            fallback = get_onnx_inference_engine(model_path=fake_file, metadata_path=meta_file)
            assert isinstance(fallback, PlaceholderEngine)

    def test_onnx_runtime_not_installed(self, tmp_path: Path):
        fake_bytes = b"valid_onnx_bytes"
        sha = hashlib.sha256(fake_bytes).hexdigest()
        fake_file = tmp_path / "model.onnx"
        fake_file.write_bytes(fake_bytes)

        meta_file = tmp_path / "manifest.json"
        meta_file.write_text(
            json.dumps({"onnx_artifact": {"sha256": sha}}),
            encoding="utf-8",
        )

        with patch.dict(sys.modules, {"onnxruntime": None}):
            engine = OnnxDetectionEngine(model_path=fake_file, metadata_path=meta_file)
            assert engine.is_ready() is False
            assert engine.session is None

            fallback = get_onnx_inference_engine(model_path=fake_file, metadata_path=meta_file)
            assert isinstance(fallback, PlaceholderEngine)

    @pytest.mark.asyncio
    async def test_invalid_image_inputs(self, tmp_path: Path):
        fake_bytes = b"valid_onnx_bytes"
        sha = hashlib.sha256(fake_bytes).hexdigest()
        fake_file = tmp_path / "model.onnx"
        fake_file.write_bytes(fake_bytes)
        meta_file = tmp_path / "manifest.json"
        meta_file.write_text(json.dumps({"onnx_artifact": {"sha256": sha}}), encoding="utf-8")

        mock_ort = MagicMock()
        mock_session = MagicMock()
        mock_input = MagicMock()
        mock_input.name = "images"
        mock_session.get_inputs.return_value = [mock_input]
        mock_ort.InferenceSession.return_value = mock_session

        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            engine = OnnxDetectionEngine(model_path=fake_file, metadata_path=meta_file)
            assert engine.is_ready() is True

            # Test None image
            res = await engine.predict(None)
            assert res.status == "error"

            # Test empty numpy array
            res_empty = await engine.predict(np.array([]))
            assert res_empty.status == "error"

    @pytest.mark.asyncio
    async def test_mocked_onnx_inference_flow(self, tmp_path: Path):
        fake_bytes = b"onnx_model_test_bytes"
        sha = hashlib.sha256(fake_bytes).hexdigest()
        fake_file = tmp_path / "model.onnx"
        fake_file.write_bytes(fake_bytes)
        meta_file = tmp_path / "manifest.json"
        meta_file.write_text(
            json.dumps({
                "model_version": "1.0.0",
                "onnx_artifact": {"sha256": sha},
            }),
            encoding="utf-8",
        )

        mock_ort = MagicMock()
        mock_session = MagicMock()
        mock_input = MagicMock()
        mock_input.name = "images"
        mock_session.get_inputs.return_value = [mock_input]

        # Simulate raw output shape [1, 5, 8400] with 1 detected egg
        mock_raw = np.zeros((1, 5, 8400), dtype=np.float32)
        mock_raw[0, 0, 100] = 320.0  # cx
        mock_raw[0, 1, 100] = 320.0  # cy
        mock_raw[0, 2, 100] = 100.0  # w
        mock_raw[0, 3, 100] = 120.0  # h
        mock_raw[0, 4, 100] = 0.945  # conf
        mock_session.run.return_value = [mock_raw]
        mock_ort.InferenceSession.return_value = mock_session

        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            engine = OnnxDetectionEngine(model_path=fake_file, metadata_path=meta_file)
            assert engine.is_ready() is True

            test_img = np.zeros((480, 640, 3), dtype=np.uint8)
            result = await engine.predict(test_img)

            assert result.status == "completed"
            assert result.confidence == 0.945
            assert result.inference_time_ms is not None
            assert result.inference_time_ms >= 0
            assert result.freshness_class is None  # Honesty check: detector does not fake candling
            assert any("Detected 1 egg(s)" in exp for exp in result.explanation)
            assert any("Primary egg localized" in exp for exp in result.explanation)


class TestModelLifecycleManager:
    """Test startup lifecycle management, local resolution, and S3 download caching."""

    @pytest.mark.asyncio
    async def test_manager_uses_local_onnx_when_available(self):
        manager = ModelLifecycleManager()
        await manager.initialize()
        # In this repository, eggvision_detector.onnx is now generated locally
        if Path("ml/artifacts/detection/weights/eggvision_detector.onnx").exists():
            assert manager.state == "MODEL_READY"
            assert manager.artifact_available is True
            assert manager.checksum_verified is True
            assert manager.runtime_name == "onnxruntime"
            assert manager.get_engine().is_ready() is True

    @pytest.mark.asyncio
    async def test_manager_integrity_failure_fallback(self, tmp_path: Path):
        fake_file = tmp_path / "bad.onnx"
        fake_file.write_bytes(b"tampered_data")

        manager = ModelLifecycleManager()
        with (
            patch("app.config.settings.MODEL_PATH", str(fake_file)),
            patch("app.config.settings.MODEL_ARTIFACT_SHA256", "non_matching_hash"),
        ):
            await manager.initialize()
            assert manager.state == "MODEL_INTEGRITY_FAILED"
            assert manager.checksum_verified is False
            assert isinstance(manager.get_engine(), PlaceholderEngine)

    @pytest.mark.asyncio
    async def test_manager_simulated_s3_download(self, tmp_path: Path):
        fake_onnx_bytes = b"downloaded_from_s3_model"
        sha = hashlib.sha256(fake_onnx_bytes).hexdigest()

        manager = ModelLifecycleManager()

        mock_s3 = MagicMock()
        def mock_download(bucket, key, dest):
            Path(dest).write_bytes(fake_onnx_bytes)
        mock_s3.download_file.side_effect = mock_download

        with (
            patch("app.config.settings.MODEL_PATH", None),
            patch("app.services.model_loader.DEFAULT_LOCAL_ONNX", tmp_path / "no_local.onnx"),
            patch("app.services.model_loader.DEFAULT_LOCAL_PT", tmp_path / "no_local.pt"),
            patch("app.config.settings.MODEL_S3_ENDPOINT", "https://s3.example.com"),
            patch("app.config.settings.MODEL_S3_BUCKET", "test-bucket"),
            patch("app.config.settings.MODEL_ARTIFACT_KEY", "eggvision/v1/model.onnx"),
            patch("app.config.settings.MODEL_S3_ACCESS_KEY", "key"),
            patch("app.config.settings.MODEL_S3_SECRET_KEY", "secret"),
            patch("app.config.settings.MODEL_ARTIFACT_SHA256", sha),
            patch("boto3.client", return_value=mock_s3),
        ):
            # Also patch OnnxDetectionEngine to avoid loading non-valid ONNX bytes
            mock_engine = MagicMock(spec=OnnxDetectionEngine)
            mock_engine.is_ready.return_value = True
            with patch("ml.inference.onnx_detection_engine.OnnxDetectionEngine", return_value=mock_engine):
                await manager.initialize()
                assert manager.state == "MODEL_READY"
                assert manager.checksum_verified is True


class TestPredictEndpointAndStorageRetrieval:
    """Test extract_storage_key and predict_scan route flow."""

    def test_extract_storage_key(self):
        assert extract_storage_key("/api/v1/artifacts/uploads/user1/scan.jpg") == "uploads/user1/scan.jpg"
        assert extract_storage_key("/uploads/scans/egg.png") == "scans/egg.png"
        assert extract_storage_key("uploads/direct/egg.jpg") == "uploads/direct/egg.jpg"
        # Traversal attacks must be blocked (return None)
        assert extract_storage_key("../../../etc/passwd") is None
        assert extract_storage_key("/api/v1/artifacts/../secret.txt") is None
        assert extract_storage_key("") is None
        assert extract_storage_key(None) is None

    @pytest.mark.asyncio
    async def test_predict_scan_404_when_missing(self):
        from fastapi import HTTPException
        mock_db = AsyncMock()
        with patch("app.services.scan_service.scan_service.get_scan", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await predict_scan(PredictRequest(scan_id=uuid.uuid4()), db=mock_db, current_user=None)
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_predict_scan_409_when_quality_poor(self):
        from fastapi import HTTPException
        mock_db = AsyncMock()
        mock_scan = MagicMock(spec=Scan)
        mock_scan.image_quality = "POOR"
        mock_scan.image_quality_warnings = ["IMAGE_TOO_DARK"]

        with patch("app.services.scan_service.scan_service.get_scan", return_value=mock_scan):
            with pytest.raises(HTTPException) as exc_info:
                await predict_scan(PredictRequest(scan_id=uuid.uuid4()), db=mock_db, current_user=None)
            assert exc_info.value.status_code == 409
            assert "image quality" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_predict_scan_e2e_with_image_retrieval(self):
        mock_db = AsyncMock()
        scan_id = uuid.uuid4()

        # Create dummy image in memory and encode as JPEG
        dummy_bgr = np.full((200, 200, 3), 180, dtype=np.uint8)
        _, jpeg_bytes = cv2.imencode(".jpg", dummy_bgr)

        mock_scan = MagicMock(spec=Scan)
        mock_scan.id = scan_id
        mock_scan.image_quality = "GOOD"
        mock_scan.image_quality_warnings = []
        mock_scan.original_image_url = "/api/v1/artifacts/uploads/user/sample.jpg"

        mock_prediction = Prediction(
            scan_id=scan_id,
            status="COMPLETED",
            model_version="1.0.0",
            confidence=0.96,
            inference_time_ms=45.2,
            explanation={
                "detection_details": ["Detected 1 egg(s) in frame."],
                "confidence": 0.96,
                "model_status": "VALIDATED",
            },
        )

        with (
            patch("app.services.scan_service.scan_service.get_scan", return_value=mock_scan),
            patch("app.services.storage_service.storage_service.get_image", return_value=(jpeg_bytes.tobytes(), "image/jpeg")),
            patch.object(prediction_service, "create_prediction", return_value=mock_prediction) as mock_create_pred,
        ):
            result = await predict_scan(
                PredictRequest(scan_id=scan_id),
                db=mock_db,
                current_user=MagicMock(spec=User),
            )

            assert result.status == "COMPLETED"
            assert result.confidence == 0.96
            # Verify create_prediction was called with decoded image array
            mock_create_pred.assert_called_once()
            call_kwargs = mock_create_pred.call_args.kwargs
            assert call_kwargs["scan_id"] == scan_id
            passed_img = call_kwargs["image"]
            assert isinstance(passed_img, np.ndarray)
            assert passed_img.shape == (200, 200, 3)
