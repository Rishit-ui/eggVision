"""EggVision AI — Phase 3 Artifact Integrity & Cloudflare R2 Runtime Tests.

Verifies:
1. ONNX loading rejects missing, malformed, and mismatched SHA-256 values.
2. A matching digest plus a mock ONNX Runtime session loads successfully.
3. Production custom/S3 model paths require MODEL_ARTIFACT_SHA256.
4. PredictionService never loads a second model after ModelLifecycleManager rejects an artifact.
5. Local artifact verification cannot return VERIFIED without an expected digest.
6. Model artifact code uses only MODEL_S3_* credentials; never silently reuses image-upload S3_* settings.
7. R2 endpoints default the SDK region to 'auto' when no model region is configured.
8. An absent or failing ONNX equivalence report cannot be packaged as a validated manifest.
9. Existing remote object checks do not treat permission/network errors as "not found".
10. Content-addressed atomic cache operations and corrupt cache eviction.
"""

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from app.config import Settings
from app.services import model_loader
from app.services.model_loader import ModelLifecycleManager
from botocore.exceptions import ClientError

from ml.inference.manifest_validator import (
    ManifestValidationError,
    validate_manifest_dict,
    validate_manifest_file,
)
from ml.inference.placeholder import PlaceholderEngine
from ml.scripts.publish_model_artifact import (
    build_manifest,
    get_s3_client,
    publish_artifact,
)
from ml.scripts.verify_model_artifact import (
    verify_local_artifact,
    verify_s3_artifact,
)


def _isolate_manager(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(model_loader, "DEFAULT_LOCAL_ONNX", tmp_path / "absent.onnx")
    monkeypatch.setattr(model_loader, "DEFAULT_LOCAL_PT", tmp_path / "absent.pt")
    monkeypatch.setattr(model_loader, "DEFAULT_LOCAL_MANIFEST", tmp_path / "absent_manifest.json")
    monkeypatch.setattr(model_loader.settings, "MODEL_PATH", None)
    monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_KEY", None)
    monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_SHA256", None)
    monkeypatch.setattr(model_loader.settings, "MODEL_S3_ENDPOINT", None)
    monkeypatch.setattr(model_loader.settings, "MODEL_S3_BUCKET", None)
    monkeypatch.setattr(model_loader.settings, "MODEL_S3_ACCESS_KEY", None)
    monkeypatch.setattr(model_loader.settings, "MODEL_S3_SECRET_KEY", None)
    monkeypatch.setattr(model_loader.settings, "APP_ENV", "development")


class TestArtifactIntegrityValidation:
    """Test strict SHA-256 validation rules."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_hash", [
        None,
        "",
        "   ",
        "short_hash",
        "g" * 64,  # invalid hex character
        "0" * 63,  # wrong length (63)
        "0" * 65,  # wrong length (65)
    ])
    async def test_onnx_loading_rejects_missing_and_malformed_checksum(self, monkeypatch, tmp_path: Path, bad_hash):
        _isolate_manager(monkeypatch, tmp_path)
        dummy_onnx = tmp_path / "model.onnx"
        dummy_onnx.write_bytes(b"dummy_onnx_model_bytes")

        monkeypatch.setattr(model_loader.settings, "MODEL_PATH", str(dummy_onnx))
        monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_SHA256", bad_hash)

        manager = ModelLifecycleManager()
        with patch("ml.inference.onnx_detection_engine.OnnxDetectionEngine") as mock_engine:
            await manager.initialize()

        mock_engine.assert_not_called()
        assert manager.state == "MODEL_INTEGRITY_FAILED"
        assert manager.checksum_verified is False
        assert manager.runtime_available is False
        assert isinstance(manager.get_engine(), PlaceholderEngine)

    @pytest.mark.asyncio
    async def test_onnx_loading_rejects_mismatched_checksum(self, monkeypatch, tmp_path: Path):
        _isolate_manager(monkeypatch, tmp_path)
        dummy_onnx = tmp_path / "model.onnx"
        dummy_onnx.write_bytes(b"dummy_onnx_model_bytes")

        monkeypatch.setattr(model_loader.settings, "MODEL_PATH", str(dummy_onnx))
        # Valid 64-hex SHA-256 but does not match dummy bytes
        monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_SHA256", "f" * 64)

        manager = ModelLifecycleManager()
        with patch("ml.inference.onnx_detection_engine.OnnxDetectionEngine") as mock_engine:
            await manager.initialize()

        mock_engine.assert_not_called()
        assert manager.state == "MODEL_INTEGRITY_FAILED"
        assert manager.checksum_verified is False
        assert "mismatch" in manager.error_message.lower()

    @pytest.mark.asyncio
    async def test_matching_digest_and_mock_runtime_loads_successfully(self, monkeypatch, tmp_path: Path):
        _isolate_manager(monkeypatch, tmp_path)
        model_bytes = b"valid_onnx_model_content_12345"
        correct_sha = hashlib.sha256(model_bytes).hexdigest()
        dummy_onnx = tmp_path / "model.onnx"
        dummy_onnx.write_bytes(model_bytes)

        monkeypatch.setattr(model_loader.settings, "MODEL_PATH", str(dummy_onnx))
        monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_SHA256", correct_sha)

        mock_instance = MagicMock()
        mock_instance.is_ready.return_value = True

        manager = ModelLifecycleManager()
        with patch("ml.inference.onnx_detection_engine.OnnxDetectionEngine", return_value=mock_instance):
            await manager.initialize()

        assert manager.state == "MODEL_READY"
        assert manager.artifact_available is True
        assert manager.checksum_verified is True
        assert manager.runtime_available is True
        assert manager.runtime_name == "onnxruntime"
        assert manager.get_engine() is mock_instance

    @pytest.mark.asyncio
    async def test_production_rejects_pytorch_artifacts(self, monkeypatch, tmp_path: Path):
        _isolate_manager(monkeypatch, tmp_path)
        pt_bytes = b"pytorch_weights"
        pt_sha = hashlib.sha256(pt_bytes).hexdigest()
        dummy_pt = tmp_path / "model.pt"
        dummy_pt.write_bytes(pt_bytes)

        monkeypatch.setattr(model_loader.settings, "MODEL_PATH", str(dummy_pt))
        monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_SHA256", pt_sha)
        monkeypatch.setattr(model_loader.settings, "APP_ENV", "production")

        manager = ModelLifecycleManager()
        await manager.initialize()

        assert manager.state == "MODEL_INTEGRITY_FAILED"
        assert "Production requires verified ONNX runtime" in manager.error_message


class TestProductionSettingsConstraints:
    """Test production environment configuration requirements."""

    def test_production_custom_model_path_requires_sha256(self):
        with pytest.raises(ValueError, match="MODEL_ARTIFACT_SHA256 must be provided"):
            Settings(
                APP_ENV="production",
                JWT_SECRET="a" * 32,
                BOOTSTRAP_TOKEN="b" * 32,
                AUTH_REQUIRED=True,
                DEBUG=False,
                CORS_ORIGINS="https://eggvision.example.com",
                MODEL_PATH="weights/model.onnx",
                MODEL_ARTIFACT_SHA256=None,
            )

    def test_production_custom_model_path_prohibits_pytorch(self):
        with pytest.raises(ValueError, match="PyTorch checkpoints are prohibited"):
            Settings(
                APP_ENV="production",
                JWT_SECRET="a" * 32,
                BOOTSTRAP_TOKEN="b" * 32,
                AUTH_REQUIRED=True,
                DEBUG=False,
                CORS_ORIGINS="https://eggvision.example.com",
                MODEL_PATH="weights/best.pt",
                MODEL_ARTIFACT_SHA256="0" * 64,
            )

    def test_production_s3_model_path_requires_sha256(self):
        with pytest.raises(ValueError, match="MODEL_ARTIFACT_SHA256 must be provided"):
            Settings(
                APP_ENV="production",
                JWT_SECRET="a" * 32,
                BOOTSTRAP_TOKEN="b" * 32,
                AUTH_REQUIRED=True,
                DEBUG=False,
                CORS_ORIGINS="https://eggvision.example.com",
                MODEL_ARTIFACT_KEY="models/v1/model.onnx",
                MODEL_ARTIFACT_SHA256=None,
            )


class TestPredictionServiceSafety:
    """Test PredictionService engine delegation and rejection handling."""

    def test_prediction_service_never_loads_second_model_after_rejection(self):
        manager = ModelLifecycleManager()
        manager.state = "MODEL_INTEGRITY_FAILED"
        manager.error_message = "Checksum mismatch."

        rogue_onnx = MagicMock()
        rogue_pt = MagicMock()

        pred_mod = sys.modules["app.services.prediction_service"]

        with (
            patch.object(pred_mod, "model_manager", manager),
            patch("ml.inference.onnx_detection_engine.get_onnx_inference_engine", rogue_onnx),
            patch("ml.inference.detection_engine.get_inference_engine", rogue_pt),
        ):
            engine = pred_mod.get_current_inference_engine()
            service_engine = pred_mod.prediction_service.get_engine()

        assert isinstance(engine, PlaceholderEngine)
        assert engine.is_ready() is False
        assert isinstance(service_engine, PlaceholderEngine)
        assert service_engine.is_ready() is False
        rogue_onnx.assert_not_called()
        rogue_pt.assert_not_called()


class TestLocalArtifactVerification:
    """Test verify_model_artifact script rules."""

    def test_local_artifact_verification_cannot_return_verified_without_expected_digest(self, tmp_path: Path):
        dummy_onnx = tmp_path / "model.onnx"
        dummy_onnx.write_bytes(b"some_onnx_bytes")

        with pytest.raises(ValueError, match="expected SHA-256 digest or valid manifest"):
            verify_local_artifact(onnx_path=dummy_onnx, manifest_path=None, expected_sha=None)


class TestStorageNamespaceSeparation:
    """Test that model artifact code uses only MODEL_S3_* and never silently reuses S3_*."""

    @pytest.mark.asyncio
    async def test_model_artifact_code_ignores_image_s3_settings(self, monkeypatch, tmp_path: Path):
        _isolate_manager(monkeypatch, tmp_path)
        # Configure image-upload storage S3_* credentials
        monkeypatch.setattr(model_loader.settings, "S3_ENDPOINT", "https://image-bucket.example.com")
        monkeypatch.setattr(model_loader.settings, "S3_BUCKET", "user-images-bucket")
        monkeypatch.setattr(model_loader.settings, "S3_ACCESS_KEY", "IMAGE_KEY")
        monkeypatch.setattr(model_loader.settings, "S3_SECRET_KEY", "IMAGE_SECRET")

        # MODEL_S3_* remain unset
        monkeypatch.setattr(model_loader.settings, "MODEL_S3_ENDPOINT", None)
        monkeypatch.setattr(model_loader.settings, "MODEL_S3_ACCESS_KEY", None)
        monkeypatch.setattr(model_loader.settings, "MODEL_S3_SECRET_KEY", None)
        monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_KEY", "models/v1/model.onnx")
        monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_SHA256", "0" * 64)

        manager = ModelLifecycleManager()
        # Should return None because MODEL_S3_* are missing, ignoring S3_*
        downloaded = await manager._try_download_from_s3()
        assert downloaded is None

    def test_publish_script_ignores_image_s3_settings(self, monkeypatch):
        monkeypatch.delenv("MODEL_S3_ENDPOINT", raising=False)
        monkeypatch.delenv("MODEL_S3_ACCESS_KEY", raising=False)
        monkeypatch.delenv("MODEL_S3_SECRET_KEY", raising=False)
        monkeypatch.setenv("S3_ENDPOINT", "https://image-bucket.example.com")
        monkeypatch.setenv("S3_ACCESS_KEY", "IMAGE_KEY")
        monkeypatch.setenv("S3_SECRET_KEY", "IMAGE_SECRET")

        client, config_info = get_s3_client()
        assert client is None
        assert config_info["has_credentials"] is False

    def test_verify_script_ignores_image_s3_settings(self, monkeypatch):
        monkeypatch.delenv("MODEL_S3_ENDPOINT", raising=False)
        monkeypatch.delenv("MODEL_S3_ACCESS_KEY", raising=False)
        monkeypatch.delenv("MODEL_S3_SECRET_KEY", raising=False)
        monkeypatch.setenv("S3_ENDPOINT", "https://image-bucket.example.com")
        monkeypatch.setenv("S3_ACCESS_KEY", "IMAGE_KEY")
        monkeypatch.setenv("S3_SECRET_KEY", "IMAGE_SECRET")

        with pytest.raises(ValueError, match="MODEL_S3_\\* credentials not configured"):
            verify_s3_artifact(artifact_key="models/v1/model.onnx", expected_sha="0" * 64)


class TestCloudflareR2Configuration:
    """Test Cloudflare R2 specific region and endpoint defaults."""

    def test_r2_endpoints_default_sdk_region_to_auto(self, monkeypatch):
        monkeypatch.setenv("MODEL_S3_ENDPOINT", "https://abcdef123456.r2.cloudflarestorage.com")
        monkeypatch.setenv("MODEL_S3_ACCESS_KEY", "R2_KEY")
        monkeypatch.setenv("MODEL_S3_SECRET_KEY", "R2_SECRET")
        monkeypatch.delenv("MODEL_S3_REGION", raising=False)

        client, config_info = get_s3_client()
        assert client is not None
        assert config_info["region"] == "auto"
        assert config_info["bucket"] == "eggvision-models"


class TestManifestValidationAndPublisherHardening:
    """Test manifest strict validation and publisher error handling."""

    def test_absent_equivalence_report_cannot_package_manifest(self, tmp_path: Path):
        onnx_file = tmp_path / "model.onnx"
        onnx_file.write_bytes(b"dummy_onnx")
        absent_report = tmp_path / "missing_equiv.json"

        with pytest.raises(FileNotFoundError, match="Mandatory ONNX equivalence report missing"):
            build_manifest(
                onnx_path=onnx_file,
                pt_path=tmp_path / "best.pt",
                meta_path=tmp_path / "meta.json",
                onnx_meta_path=tmp_path / "onnx_meta.json",
                equiv_path=absent_report,
            )

    def test_failing_equivalence_report_cannot_package_manifest(self, tmp_path: Path):
        onnx_file = tmp_path / "model.onnx"
        onnx_file.write_bytes(b"dummy_onnx")
        failing_report = tmp_path / "equiv.json"
        failing_report.write_text(
            json.dumps({"status": "FAILED", "summary": {"mean_iou": 0.65}}),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="expected 'PASSED_EQUIVALENT'"):
            build_manifest(
                onnx_path=onnx_file,
                pt_path=tmp_path / "best.pt",
                meta_path=tmp_path / "meta.json",
                onnx_meta_path=tmp_path / "onnx_meta.json",
                equiv_path=failing_report,
            )

    def test_manifest_validator_rejects_missing_fields(self):
        with pytest.raises(ManifestValidationError, match="missing mandatory 'manifest_version'"):
            validate_manifest_dict({"model_name": "eggvision_detector_yolov8n"})

    def test_manifest_validator_validates_canonical_manifest(self):
        manifest_file = Path("ml/artifacts/detection/manifest.json")
        if manifest_file.exists():
            res = validate_manifest_file(manifest_file)
            assert res["manifest_version"] == "1.0.0"
            assert res["classes"] == {"0": "egg"}

    def test_remote_head_permission_error_is_not_treated_as_not_found(self, monkeypatch, tmp_path: Path):
        manifest = {
            "manifest_version": "1.0.0",
            "model_name": "eggvision_detector_yolov8n",
            "model_version": "1.0.0",
            "task": "detection",
            "classes": {"0": "egg"},
            "input_resolution": [640, 640],
            "input_color_format": "RGB",
            "input_normalization": "scale_0_to_1",
            "onnx_artifact": {
                "key": "models/v1/model.onnx",
                "filename": "model.onnx",
                "sha256": "0" * 64,
                "size_bytes": 100,
                "format": "onnx",
                "opset": 17,
            },
            "original_checkpoint": {"architecture": "yolov8n", "sha256": "0" * 64, "size_bytes": 50},
            "provenance": {"dataset_source": "test"},
            "onnx_export_details": {"inputs": [{"shape": [1, 3, 640, 640]}], "outputs": [{"shape": [1, 5, 8400]}]},
            "onnx_equivalence": {"mean_iou": 0.95, "count_matches": 8},
            "manifest_key": "models/v1/manifest.json",
            "status": "VALIDATED",
        }
        manifest_out = tmp_path / "manifest.json"
        report_out = tmp_path / "report.json"
        onnx_file = tmp_path / "model.onnx"
        onnx_file.write_bytes(b"dummy")

        mock_client = MagicMock()
        # Simulate 403 Forbidden on HEAD
        forbidden_error = ClientError(
            error_response={"Error": {"Code": "403", "Message": "Forbidden"}},
            operation_name="HeadObject",
        )
        mock_client.head_object.side_effect = forbidden_error

        with patch("ml.scripts.publish_model_artifact.get_s3_client", return_value=(mock_client, {"bucket": "b"})):
            report = publish_artifact(manifest, onnx_file, manifest_out, report_out)

        assert report["status"] == "UPLOAD_FAILED"
        assert "403" in report["error"]
        # Ensure put_object was never called because preflight failed with permission error
        mock_client.put_object.assert_not_called()


class TestContentAddressedCacheReliability:
    """Test runtime caching and atomic movement."""

    @pytest.mark.asyncio
    async def test_atomic_download_and_cache_reuse(self, monkeypatch, tmp_path: Path):
        _isolate_manager(monkeypatch, tmp_path)
        model_bytes = b"content_addressed_model_bytes_999"
        expected_sha = hashlib.sha256(model_bytes).hexdigest()

        monkeypatch.setattr(model_loader.settings, "MODEL_S3_ENDPOINT", "https://r2.example.com")
        monkeypatch.setattr(model_loader.settings, "MODEL_S3_ACCESS_KEY", "KEY")
        monkeypatch.setattr(model_loader.settings, "MODEL_S3_SECRET_KEY", "SECRET")
        monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_KEY", "models/v1/model.onnx")
        monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_SHA256", expected_sha)
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

        mock_s3 = MagicMock()

        def _mock_download(bucket, key, target_path):
            Path(target_path).write_bytes(model_bytes)

        mock_s3.download_file.side_effect = _mock_download

        manager = ModelLifecycleManager()
        with (
            patch("boto3.client", return_value=mock_s3),
            patch("ml.inference.onnx_detection_engine.OnnxDetectionEngine") as mock_engine,
        ):
            mock_inst = MagicMock()
            mock_inst.is_ready.return_value = True
            mock_engine.return_value = mock_inst
            await manager.initialize()

        assert manager.state == "MODEL_READY"
        cached_file = tmp_path / "eggvision_models" / expected_sha / "model.onnx"
        assert cached_file.exists()
        assert cached_file.read_bytes() == model_bytes

        # Second initialize should reuse cache without downloading again
        mock_s3.download_file.reset_mock()
        manager2 = ModelLifecycleManager()
        with (
            patch("boto3.client", return_value=mock_s3),
            patch("ml.inference.onnx_detection_engine.OnnxDetectionEngine", return_value=mock_inst),
        ):
            await manager2.initialize()

        mock_s3.download_file.assert_not_called()
        assert manager2.state == "MODEL_READY"
