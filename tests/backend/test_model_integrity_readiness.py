"""Production-readiness tests for model artifact integrity and engine selection."""

import hashlib
import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from app.routers import model_info as model_info_router
from app.services import model_loader
from app.services.model_loader import ModelLifecycleManager

from ml.inference.engine import ModelInfo
from ml.inference.placeholder import PlaceholderEngine

prediction_service_module = importlib.import_module("app.services.prediction_service")


def configure_isolated_artifact(monkeypatch, tmp_path: Path, artifact: Path, checksum: str | None) -> None:
    monkeypatch.setattr(model_loader.settings, "MODEL_PATH", str(artifact))
    monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_SHA256", checksum)
    monkeypatch.setattr(model_loader, "DEFAULT_LOCAL_ONNX", tmp_path / "absent-default.onnx")
    monkeypatch.setattr(model_loader, "DEFAULT_LOCAL_PT", tmp_path / "absent-default.pt")
    monkeypatch.setattr(model_loader, "DEFAULT_LOCAL_MANIFEST", tmp_path / "absent-manifest.json")
    monkeypatch.setattr(model_loader.settings, "MODEL_S3_ENDPOINT", None)
    monkeypatch.setattr(model_loader.settings, "MODEL_S3_BUCKET", None)
    monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_KEY", None)
    monkeypatch.setattr(model_loader.settings, "MODEL_S3_ACCESS_KEY", None)
    monkeypatch.setattr(model_loader.settings, "MODEL_S3_SECRET_KEY", None)


@pytest.mark.asyncio
async def test_missing_expected_checksum_rejects_before_runtime(monkeypatch, tmp_path: Path):
    artifact = tmp_path / "model.onnx"
    artifact.write_bytes(b"model-without-declared-checksum")
    configure_isolated_artifact(monkeypatch, tmp_path, artifact, None)
    manager = ModelLifecycleManager()

    with patch("ml.inference.onnx_detection_engine.OnnxDetectionEngine") as runtime:
        await manager.initialize()

    runtime.assert_not_called()
    assert manager.state == "MODEL_INTEGRITY_FAILED"
    assert manager.artifact_available is True
    assert manager.checksum_verified is False
    assert manager.runtime_available is False
    assert manager.get_status_summary()["is_ready"] is False
    assert isinstance(manager.get_engine(), PlaceholderEngine)


@pytest.mark.asyncio
async def test_checksum_mismatch_rejects_before_runtime(monkeypatch, tmp_path: Path):
    artifact = tmp_path / "model.onnx"
    artifact.write_bytes(b"model-with-wrong-checksum")
    configure_isolated_artifact(monkeypatch, tmp_path, artifact, "0" * 64)
    manager = ModelLifecycleManager()

    with patch("ml.inference.onnx_detection_engine.OnnxDetectionEngine") as runtime:
        await manager.initialize()

    runtime.assert_not_called()
    assert manager.state == "MODEL_INTEGRITY_FAILED"
    assert manager.checksum_verified is False
    assert manager.runtime_available is False
    assert isinstance(manager.get_engine(), PlaceholderEngine)


@pytest.mark.asyncio
async def test_exact_checksum_and_runtime_success_are_both_required(monkeypatch, tmp_path: Path):
    contents = b"integrity-verified-model"
    artifact = tmp_path / "model.onnx"
    artifact.write_bytes(contents)
    configure_isolated_artifact(monkeypatch, tmp_path, artifact, hashlib.sha256(contents).hexdigest())
    manager = ModelLifecycleManager()
    verified_engine = MagicMock()
    verified_engine.is_ready.return_value = True

    with patch("ml.inference.onnx_detection_engine.OnnxDetectionEngine", return_value=verified_engine):
        await manager.initialize()

    assert manager.state == "MODEL_READY"
    assert manager.artifact_available is True
    assert manager.checksum_verified is True
    assert manager.runtime_available is True
    assert manager.runtime_name == "onnxruntime"
    assert manager.get_status_summary()["is_ready"] is True
    assert manager.get_engine() is verified_engine


@pytest.mark.asyncio
async def test_missing_artifact_never_initializes_runtime(monkeypatch, tmp_path: Path):
    artifact = tmp_path / "missing.onnx"
    configure_isolated_artifact(monkeypatch, tmp_path, artifact, "0" * 64)
    manager = ModelLifecycleManager()

    with patch("ml.inference.onnx_detection_engine.OnnxDetectionEngine") as runtime:
        await manager.initialize()

    runtime.assert_not_called()
    assert manager.state == "MODEL_NOT_READY"
    assert manager.artifact_available is False
    assert manager.checksum_verified is False
    assert manager.runtime_available is False
    assert isinstance(manager.get_engine(), PlaceholderEngine)


@pytest.mark.asyncio
async def test_onnx_initialization_failure_preserves_verification_but_not_readiness(monkeypatch, tmp_path: Path):
    contents = b"verified-model-runtime-cannot-load"
    artifact = tmp_path / "model.onnx"
    artifact.write_bytes(contents)
    configure_isolated_artifact(monkeypatch, tmp_path, artifact, hashlib.sha256(contents).hexdigest())
    manager = ModelLifecycleManager()

    with patch(
        "ml.inference.onnx_detection_engine.OnnxDetectionEngine",
        side_effect=RuntimeError("simulated ONNX initialization failure"),
    ):
        await manager.initialize()

    assert manager.state == "MODEL_ERROR"
    assert manager.artifact_available is True
    assert manager.checksum_verified is True
    assert manager.runtime_available is False
    assert manager.runtime_name is None
    assert manager.get_status_summary()["is_ready"] is False
    assert isinstance(manager.get_engine(), PlaceholderEngine)


def test_prediction_engine_cannot_bypass_lifecycle_validation():
    manager = ModelLifecycleManager()
    unverified_ready_engine = MagicMock()
    unverified_ready_engine.is_ready.return_value = True
    manager.engine = unverified_ready_engine
    manager.state = "MODEL_NOT_READY"
    manager.artifact_available = True
    manager.checksum_verified = False
    manager.runtime_available = False

    rogue_onnx = MagicMock()
    rogue_pytorch = MagicMock()
    with (
        patch.object(prediction_service_module, "model_manager", manager),
        patch("ml.inference.onnx_detection_engine.get_onnx_inference_engine", rogue_onnx),
        patch("ml.inference.detection_engine.get_inference_engine", rogue_pytorch),
    ):
        selected = prediction_service_module.get_current_inference_engine()

    assert isinstance(selected, PlaceholderEngine)
    assert selected.is_ready() is False
    rogue_onnx.assert_not_called()
    rogue_pytorch.assert_not_called()


@pytest.mark.asyncio
async def test_model_info_reports_lifecycle_verification_state():
    manager = ModelLifecycleManager()
    manager.state = "MODEL_INTEGRITY_FAILED"
    manager.artifact_available = True
    manager.checksum_verified = False
    manager.runtime_available = False
    manager.error_message = "Expected SHA-256 checksum is missing."

    with patch.object(model_info_router, "model_manager", manager):
        response = await model_info_router.get_model_info()

    assert response.state == "MODEL_INTEGRITY_FAILED"
    assert response.artifact_available is True
    assert response.checksum_verified is False
    assert response.runtime_available is False
    assert response.is_ready is False
    assert response.model_type == "placeholder"


@pytest.mark.asyncio
async def test_model_info_reports_ready_only_for_fully_verified_runtime():
    manager = ModelLifecycleManager()
    verified_engine = MagicMock()
    verified_engine.is_ready.return_value = True
    verified_engine.get_model_info.return_value = ModelInfo(
        version="phase2-test",
        model_type="yolov8n_onnx_detection",
        is_ready=True,
        description="Verified test runtime.",
    )
    manager.engine = verified_engine
    manager.state = "MODEL_READY"
    manager.artifact_available = True
    manager.checksum_verified = True
    manager.runtime_available = True
    manager.runtime_name = "onnxruntime"

    with patch.object(model_info_router, "model_manager", manager):
        response = await model_info_router.get_model_info()

    assert response.state == "MODEL_READY"
    assert response.artifact_available is True
    assert response.checksum_verified is True
    assert response.runtime_available is True
    assert response.runtime_name == "onnxruntime"
    assert response.is_ready is True


@pytest.mark.asyncio
async def test_https_release_asset_is_downloaded_verified_and_loaded(monkeypatch, tmp_path: Path):
    import io

    contents = b"verified-release-model"
    expected_sha = hashlib.sha256(contents).hexdigest()
    monkeypatch.setattr(model_loader.settings, "MODEL_PATH", None)
    monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_URL", "https://github.com/example/repo/releases/download/v1/model.onnx")
    monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_SHA256", expected_sha)
    monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_MAX_BYTES", 1024)
    monkeypatch.setattr(model_loader.settings, "MODEL_S3_ENDPOINT", None)
    monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_KEY", None)
    monkeypatch.setattr(model_loader, "DEFAULT_LOCAL_ONNX", tmp_path / "absent.onnx")
    monkeypatch.setattr(model_loader, "DEFAULT_LOCAL_PT", tmp_path / "absent.pt")
    monkeypatch.setattr(model_loader, "DEFAULT_LOCAL_MANIFEST", tmp_path / "absent.json")
    monkeypatch.setattr(model_loader.tempfile, "gettempdir", lambda: str(tmp_path))

    response = io.BytesIO(contents)
    response.status = 200
    response.headers = {"Content-Length": str(len(contents))}
    response.geturl = lambda: "https://github.com/example/repo/releases/download/v1/model.onnx"
    manager = ModelLifecycleManager()
    engine = MagicMock()
    engine.is_ready.return_value = True

    with (
        patch.object(model_loader, "urlopen", return_value=response),
        patch("ml.inference.onnx_detection_engine.OnnxDetectionEngine", return_value=engine),
    ):
        await manager.initialize()

    assert manager.state == "MODEL_READY"
    assert manager.checksum_verified is True
    assert manager.resolved_model_path is not None
    assert manager.resolved_model_path.read_bytes() == contents
    assert manager.get_engine() is engine


@pytest.mark.asyncio
async def test_https_release_asset_checksum_mismatch_is_rejected(monkeypatch, tmp_path: Path):
    import io

    contents = b"tampered-release-model"
    monkeypatch.setattr(model_loader.settings, "MODEL_PATH", None)
    monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_URL", "https://github.com/example/repo/releases/download/v1/model.onnx")
    monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_SHA256", "0" * 64)
    monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_MAX_BYTES", 1024)
    monkeypatch.setattr(model_loader.settings, "MODEL_S3_ENDPOINT", None)
    monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_KEY", None)
    monkeypatch.setattr(model_loader, "DEFAULT_LOCAL_ONNX", tmp_path / "absent.onnx")
    monkeypatch.setattr(model_loader, "DEFAULT_LOCAL_PT", tmp_path / "absent.pt")
    monkeypatch.setattr(model_loader, "DEFAULT_LOCAL_MANIFEST", tmp_path / "absent.json")
    monkeypatch.setattr(model_loader.tempfile, "gettempdir", lambda: str(tmp_path))

    response = io.BytesIO(contents)
    response.status = 200
    response.headers = {"Content-Length": str(len(contents))}
    response.geturl = lambda: "https://github.com/example/repo/releases/download/v1/model.onnx"
    manager = ModelLifecycleManager()

    with (
        patch.object(model_loader, "urlopen", return_value=response),
        patch("ml.inference.onnx_detection_engine.OnnxDetectionEngine") as runtime,
    ):
        await manager.initialize()

    runtime.assert_not_called()
    assert manager.state == "MODEL_INTEGRITY_FAILED"
    assert manager.checksum_verified is False
    assert isinstance(manager.get_engine(), PlaceholderEngine)


@pytest.mark.asyncio
async def test_https_release_asset_rejects_non_https_url(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(model_loader.settings, "MODEL_PATH", None)
    monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_URL", "http://example.com/model.onnx")
    monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_SHA256", "a" * 64)
    monkeypatch.setattr(model_loader.settings, "MODEL_S3_ENDPOINT", None)
    monkeypatch.setattr(model_loader.settings, "MODEL_ARTIFACT_KEY", None)
    monkeypatch.setattr(model_loader, "DEFAULT_LOCAL_ONNX", tmp_path / "absent.onnx")
    monkeypatch.setattr(model_loader, "DEFAULT_LOCAL_PT", tmp_path / "absent.pt")
    monkeypatch.setattr(model_loader, "DEFAULT_LOCAL_MANIFEST", tmp_path / "absent.json")
    manager = ModelLifecycleManager()

    with patch.object(model_loader, "urlopen") as download:
        await manager.initialize()

    download.assert_not_called()
    assert manager.state == "MODEL_INTEGRITY_FAILED"
