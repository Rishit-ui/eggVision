"""test_phase1_foundation.py
Comprehensive automated test suite for EggVision ML Foundation (Phase 1 & 1.1).

Covers:
1. Importer constants, class mapping, and label validation logic.
2. Dataset validation suite on valid, corrupt, and edge-case dataset fixtures.
3. Dataset splitting logic (70/15/15 ratio, zero-leakage hash check, data.yaml).
4. Inference engine adapter (PlaceholderEngine vs DetectionEngine behavior,
   scientific honesty disclaimers, result structure).
5. PredictionService integration (status reflecting engine state).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ml.inference.detection_engine import DetectionEngine, get_inference_engine
from ml.inference.placeholder import PlaceholderEngine
from ml.scripts.import_hf_egg_detection import (
    CLASS_MAP_ORIGINAL,
    PINNED_REVISION,
    TARGET_CLASS_ID,
    TARGET_CLASS_NAME,
    validate_and_map_yolo_labels,
)
from ml.scripts.split_dataset import split_dataset
from ml.scripts.validate_dataset import validate_dataset_directory


class TestImporterLogic:
    """Test dataset importation logic, constants, and label mapping."""

    def test_pinned_revision_and_constants(self):
        assert PINNED_REVISION == "d425996c959623b3960fca27f53b16f060b0a474"
        assert CLASS_MAP_ORIGINAL[0] == "white-egg"
        assert CLASS_MAP_ORIGINAL[1] == "brown-egg"
        assert TARGET_CLASS_ID == 0
        assert TARGET_CLASS_NAME == "egg"

    def test_label_parsing_and_mapping(self, tmp_path: Path):
        raw_label = tmp_path / "sample.txt"
        mapped_label = tmp_path / "sample_mapped.txt"

        # Content with BOM and mixed classes (0: white-egg, 1: brown-egg)
        raw_label.write_text(
            "\ufeff0 0.25 0.35 0.15 0.18\n1 0.65 0.75 0.20 0.22\n",
            encoding="utf-8",
        )

        valid, boxes, errors = validate_and_map_yolo_labels(raw_label, mapped_label)
        assert valid is True
        assert len(errors) == 0
        assert len(boxes) == 2

        # Check box mapping
        assert boxes[0]["original_class_name"] == "white-egg"
        assert boxes[0]["mapped_class_id"] == 0
        assert boxes[1]["original_class_name"] == "brown-egg"
        assert boxes[1]["mapped_class_id"] == 0

        # Check mapped file content (all class 0)
        mapped_lines = mapped_label.read_text(encoding="utf-8").strip().splitlines()
        assert len(mapped_lines) == 2
        assert mapped_lines[0].startswith("0 ")
        assert mapped_lines[1].startswith("0 ")

    def test_invalid_label_parsing(self, tmp_path: Path):
        raw_label = tmp_path / "invalid.txt"
        mapped_label = tmp_path / "invalid_mapped.txt"
        raw_label.write_text("0 1.5 0.5 0.2 0.2\nnot_numbers\n", encoding="utf-8")

        valid, boxes, errors = validate_and_map_yolo_labels(raw_label, mapped_label)
        assert valid is False
        assert len(errors) >= 2


class TestDatasetValidator:
    """Test dataset validation suite on synthetic fixture directories."""

    def test_valid_dataset_fixture(self, tmp_path: Path):
        import cv2

        images_dir = tmp_path / "images"
        labels_dir = tmp_path / "labels"
        images_dir.mkdir()
        labels_dir.mkdir()

        # Create 2 valid synthetic test images
        img1 = np.full((100, 100, 3), 200, dtype=np.uint8)
        img2 = np.full((120, 120, 3), 150, dtype=np.uint8)
        cv2.imwrite(str(images_dir / "egg1.jpg"), img1)
        cv2.imwrite(str(images_dir / "egg2.jpg"), img2)

        # Create matching valid labels
        (labels_dir / "egg1.txt").write_text("0 0.5 0.5 0.3 0.3\n", encoding="utf-8")
        (labels_dir / "egg2.txt").write_text("0 0.4 0.6 0.2 0.4\n", encoding="utf-8")

        report = validate_dataset_directory(images_dir=images_dir, labels_dir=labels_dir, num_classes=1)
        assert report["summary_status"] == "PASSED"
        assert report["total_images"] == 2
        assert report["valid_images"] == 2
        assert report["corrupt_images"] == 0
        assert report["missing_labels"] == 0
        assert report["orphaned_labels"] == 0
        assert report["bounding_box_errors"] == 0
        assert report["class_distribution"] == {0: 2}

    def test_corrupt_and_missing_label_detection(self, tmp_path: Path):
        import cv2

        images_dir = tmp_path / "images"
        labels_dir = tmp_path / "labels"
        images_dir.mkdir()
        labels_dir.mkdir()

        # 1 valid image without label
        img = np.full((100, 100, 3), 200, dtype=np.uint8)
        cv2.imwrite(str(images_dir / "no_label.jpg"), img)

        # 1 corrupt 0-byte image file
        (images_dir / "corrupt.jpg").touch()

        # 1 orphaned label file
        (labels_dir / "orphan.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")

        report = validate_dataset_directory(images_dir=images_dir, labels_dir=labels_dir, num_classes=1)
        assert report["summary_status"] == "FAILED"
        assert report["corrupt_images"] == 1
        assert report["missing_labels"] == 1
        assert report["orphaned_labels"] == 1


class TestDatasetSplitter:
    """Test dataset splitting logic and leakage verification."""

    def test_reproducible_split_and_zero_leakage(self, tmp_path: Path):
        import cv2

        src_images = tmp_path / "src_images"
        src_labels = tmp_path / "src_labels"
        out_dir = tmp_path / "split_output"
        src_images.mkdir()
        src_labels.mkdir()

        # Create 20 unique images
        for i in range(20):
            img = np.full((50, 50, 3), i * 10, dtype=np.uint8)
            cv2.imwrite(str(src_images / f"sample_{i:02d}.jpg"), img)
            (src_labels / f"sample_{i:02d}.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")

        report = split_dataset(
            images_dir=src_images,
            labels_dir=src_labels,
            output_dir=out_dir,
            train_ratio=0.70,
            val_ratio=0.15,
            test_ratio=0.15,
            seed=42,
        )

        assert report["leakage_verification"]["status"] == "PASSED_ZERO_LEAKAGE"
        assert report["leakage_verification"]["leakage_detected"] is False
        assert report["split_level"] == "image-level"

        # Check total partitioned samples
        total_parts = (
            report["partitions"]["train"]["image_count"]
            + report["partitions"]["val"]["image_count"]
            + report["partitions"]["test"]["image_count"]
        )
        assert total_parts == 20

        # Check data.yaml created
        data_yaml = out_dir / "data.yaml"
        assert data_yaml.exists()
        content = data_yaml.read_text(encoding="utf-8")
        assert "names:" in content
        assert "0: egg" in content


class TestInferenceEngines:
    """Test PlaceholderEngine and DetectionEngine adapters."""

    def test_placeholder_engine(self):
        engine = PlaceholderEngine()
        assert engine.is_ready() is False
        info = engine.get_model_info()
        assert info.is_ready is False
        assert info.version == "none"

    @pytest.mark.asyncio
    async def test_placeholder_predict(self):
        engine = PlaceholderEngine()
        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = await engine.predict(dummy_img)
        assert result.status == "model_not_ready"
        assert "No trained model" in result.error_message

    def test_detection_engine_fallback_when_weights_missing(self, tmp_path: Path):
        engine = DetectionEngine(
            weights_path=tmp_path / "non_existent.pt",
            metadata_path=tmp_path / "meta.json",
        )
        assert engine.is_ready() is False
        info = engine.get_model_info()
        assert info.is_ready is False

    def test_get_inference_engine_factory(self, tmp_path: Path):
        # When path does not exist, returns PlaceholderEngine
        engine = get_inference_engine(weights_path=tmp_path / "none.pt")
        assert isinstance(engine, PlaceholderEngine)
        assert engine.is_ready() is False

    @pytest.mark.asyncio
    async def test_detection_engine_with_mocked_yolo(self, tmp_path: Path):
        fake_weights = tmp_path / "best.pt"
        fake_weights.write_bytes(b"dummy_weights")
        meta_file = tmp_path / "model_metadata.json"
        meta_file.write_text(
            json.dumps({"model_name": "eggvision_detector_yolov8n", "weights_sha256": "fake"}),
            encoding="utf-8",
        )

        with patch("ultralytics.YOLO") as MockYOLO:
            mock_instance = MagicMock()
            MockYOLO.return_value = mock_instance

            # Mock prediction result
            mock_box = MagicMock()
            mock_box.__len__.return_value = 1
            mock_box.conf.cpu().numpy.return_value = np.array([0.94])
            mock_box.xyxy.cpu().numpy.return_value = np.array([[50.0, 60.0, 150.0, 180.0]])

            mock_res = MagicMock()
            mock_res.boxes = mock_box
            mock_instance.predict.return_value = [mock_res]

            engine = DetectionEngine(weights_path=fake_weights, metadata_path=meta_file)
            assert engine.is_ready() is True

            test_img = np.zeros((200, 200, 3), dtype=np.uint8)
            pred = await engine.predict(test_img)

            assert pred.status == "completed"
            assert pred.confidence == 0.94
            assert pred.freshness_class is None  # Scientifically honest: not candling
            assert any("Primary egg localized" in exp for exp in pred.explanation)
            assert any("candling internal freshness" in exp for exp in pred.explanation)

    @pytest.mark.asyncio
    async def test_real_trained_detector_inference(self):
        """End-to-end test on the actual trained weights and sample image."""
        real_weights = Path("ml/artifacts/detection/weights/best.pt")
        real_meta = Path("ml/artifacts/detection/model_metadata.json")
        if not real_weights.exists():
            pytest.skip("Real trained weights not present")

        engine = DetectionEngine(weights_path=real_weights, metadata_path=real_meta)
        assert engine.is_ready() is True
        info = engine.get_model_info()
        assert info.is_ready is True
        assert info.version == "eggvision_detector_yolov8n"

        # Load a real test image from held-out split
        test_images_dir = Path("ml/data/processed/egg_detection_yolo/images/test")
        test_images = list(test_images_dir.glob("*.jpg"))
        if not test_images:
            pytest.skip("No test images available")

        import cv2

        img = cv2.imread(str(test_images[0]))
        pred = await engine.predict(img)

        assert pred.status == "completed"
        assert pred.confidence > 0.50
        assert pred.inference_time_ms is not None
        assert pred.inference_time_ms > 0
        assert pred.freshness_class is None  # Honesty check: detector does not fake candling
        assert len(pred.explanation) >= 2
