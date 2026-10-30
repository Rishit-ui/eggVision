"""CV Service for Backend Pipeline Integration.

Decodes incoming raw image uploads, executes VisionPipeline,
and generates processed/normalized image artifacts for storage.
"""

import asyncio
import logging
import uuid
from time import perf_counter
from typing import Any
import cv2
import numpy as np

from ml.vision.pipeline import VisionPipeline, PipelineResult
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)


class CVService:
    """Service bridge connecting FastAPI endpoints with the ML vision pipeline."""

    def __init__(self):
        self.pipeline = VisionPipeline()

    async def process_scan_image(self, image_bytes: bytes, original_filename: str, correlation_id: str) -> dict[str, Any]:
        """Decode image bytes, run CV quality and normalization, and upload processed image.
        
        Returns:
            Dictionary containing:
            - image_quality: "GOOD" | "ACCEPTABLE" | "POOR"
            - quality_score: deprecated and always None; not a confidence score
            - warnings: list[str]
            - retake_recommended: bool
            - recommendation: Optional[str]
            - processed_image_url: Optional[str]
            - geometry: Optional[dict]
            - can_proceed_to_inference: bool
        """
        started = perf_counter()
        # Decode byte buffer into OpenCV BGR numpy array. Only dimensions are
        # logged; image bytes and the client filename are never logged.
        image_bgr = await asyncio.to_thread(
            cv2.imdecode, np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR
        )

        if image_bgr is None:
            return {
                "image_quality": "POOR",
                "quality_score": None,
                "warnings": ["INVALID_IMAGE_DATA"],
                "retake_recommended": True,
                "recommendation": "The uploaded file could not be parsed as a valid image.",
                "processed_image_url": None,
                "geometry": None,
                "candidate_geometry": None,
                "analysis": {
                    "status": "INVALID_IMAGE",
                    "model": None,
                    "detections": [],
                    "limitations": ["The uploaded bytes could not be decoded as an image."],
                    "message": "The uploaded file could not be parsed as a valid image.",
                },
                "can_proceed_to_inference": False
            }
        logger.info(
            "scan_stage=image_decoded request_id=%s elapsed_ms=%.2f width=%s height=%s",
            correlation_id, (perf_counter() - started) * 1000, image_bgr.shape[1], image_bgr.shape[0],
        )

        logger.info("scan_stage=cv_processing_started request_id=%s", correlation_id)
        cv_started = perf_counter()
        try:
            # VisionPipeline is synchronous and CPU-bound. Keep it off the
            # FastAPI event loop so other requests can continue while it runs.
            result: PipelineResult = await asyncio.to_thread(self.pipeline.process, image_bgr)
        except Exception:
            logger.exception("scan_failed request_id=%s category=cv_processing", correlation_id)
            raise
        logger.info(
            "scan_stage=cv_processing_completed request_id=%s elapsed_ms=%.2f",
            correlation_id, (perf_counter() - cv_started) * 1000,
        )
        pipeline_dict = result.to_dict()

        processed_url = None
        if result.normalization and result.normalization.success:
            # Encode canonical normalized image to JPEG
            norm_img = result.normalization.normalized_image
            success, encoded_buf = await asyncio.to_thread(
                cv2.imencode, ".jpg", norm_img, [cv2.IMWRITE_JPEG_QUALITY, 95]
            )
            if success:
                norm_filename = f"normalized_{uuid.uuid4()}.jpg"
                try:
                    processed_url = await storage_service.upload_image(encoded_buf.tobytes(), norm_filename, "image/jpeg")
                except Exception:
                    logger.exception("scan_failed request_id=%s category=normalized_image_storage", correlation_id)
                    raise
                logger.info("scan_stage=normalized_image_storage_completed request_id=%s", correlation_id)

        pipeline_dict["processed_image_url"] = processed_url
        return pipeline_dict


cv_service = CVService()
