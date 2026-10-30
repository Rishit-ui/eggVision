
"""
CV Service for Backend Pipeline Integration.

Decodes incoming image uploads, executes VisionPipeline,
and generates processed/normalized image artifacts for storage.
"""

import asyncio
import logging
import uuid
from time import perf_counter
from typing import Any

import cv2
import numpy as np

from ml.vision.pipeline import PipelineResult, VisionPipeline
from app.services.storage_service import storage_service


logger = logging.getLogger(__name__)


class CVService:
    """Connects FastAPI scan requests with the vision pipeline."""

    def __init__(self, max_concurrent_processing: int = 1) -> None:
        self.pipeline = VisionPipeline()

        # Limit simultaneous CV operations to protect
        # low-resource deployment instances.
        self._processing_semaphore = asyncio.Semaphore(
            max_concurrent_processing
        )

    async def process_scan_image(
        self,
        image_bytes: bytes,
        original_filename: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        """
        Decode, process, and optionally store a normalized image.

        The original image is expected to be stored by the caller.

        Returns the existing pipeline response structure with
        the processed_image_url field.
        """

        total_started = perf_counter()

        # STEP 1: Decode image without blocking the event loop.
        decode_started = perf_counter()

        try:
            image_array = np.frombuffer(
                image_bytes,
                dtype=np.uint8,
            )

            image_bgr = await asyncio.to_thread(
                cv2.imdecode,
                image_array,
                cv2.IMREAD_COLOR,
            )

        except Exception:
            logger.exception(
                "scan_failed request_id=%s category=image_decode",
                correlation_id,
            )
            raise

        # Handle invalid image data.
        if image_bgr is None:
            logger.warning(
                "scan_rejected request_id=%s category=invalid_image_data",
                correlation_id,
            )

            return {
                "image_quality": "POOR",
                "quality_score": None,
                "warnings": ["INVALID_IMAGE_DATA"],
                "retake_recommended": True,
                "recommendation": (
                    "The uploaded file could not be parsed "
                    "as a valid image."
                ),
                "processed_image_url": None,
                "geometry": None,
                "candidate_geometry": None,
                "analysis": {
                    "status": "INVALID_IMAGE",
                    "model": None,
                    "detections": [],
                    "limitations": [
                        "The uploaded bytes could not be "
                        "decoded as an image."
                    ],
                    "message": "Invalid image data.",
                },
                "can_proceed_to_inference": False,
            }

        height, width = image_bgr.shape[:2]

        logger.info(
            "scan_stage=image_decoded request_id=%s "
            "elapsed_ms=%.2f width=%d height=%d",
            correlation_id,
            (perf_counter() - decode_started) * 1000,
            width,
            height,
        )

        # STEP 2: Execute the synchronous CV pipeline
        # in a worker thread instead of blocking FastAPI.
        cv_started = perf_counter()

        logger.info(
            "scan_stage=cv_processing_started request_id=%s",
            correlation_id,
        )

        try:
            async with self._processing_semaphore:
                result: PipelineResult = await asyncio.to_thread(
                    self.pipeline.process,
                    image_bgr,
                )

        except Exception:
            logger.exception(
                "scan_failed request_id=%s category=cv_processing",
                correlation_id,
            )
            raise

        logger.info(
            "scan_stage=cv_processing_completed request_id=%s "
            "elapsed_ms=%.2f",
            correlation_id,
            (perf_counter() - cv_started) * 1000,
        )

        # STEP 3: Convert pipeline output into the existing response.
        try:
            pipeline_dict = result.to_dict()

        except Exception:
            logger.exception(
                "scan_failed request_id=%s category=result_serialization",
                correlation_id,
            )
            raise

        # STEP 4: Upload normalized image when available.
        processed_url = None

        normalization = result.normalization

        if normalization and normalization.success:

            encode_started = perf_counter()

            try:
                normalized_image = normalization.normalized_image

                success, encoded_buffer = await asyncio.to_thread(
                    cv2.imencode,
                    ".jpg",
                    normalized_image,
                    [cv2.IMWRITE_JPEG_QUALITY, 95],
                )

            except Exception:
                logger.exception(
                    "scan_failed request_id=%s "
                    "category=normalized_image_encoding",
                    correlation_id,
                )
                raise

            encode_elapsed_ms = (
                perf_counter() - encode_started
            ) * 1000

            if not success:
                logger.warning(
                    "scan_warning request_id=%s "
                    "category=normalized_image_encoding_failed",
                    correlation_id,
                )

            else:
                encoded_bytes = encoded_buffer.tobytes()

                normalized_filename = (
                    f"normalized_{uuid.uuid4()}.jpg"
                )

                storage_started = perf_counter()

                try:
                    processed_url = (
                        await storage_service.upload_image(
                            encoded_bytes,
                            normalized_filename,
                            "image/jpeg",
                        )
                    )

                except Exception:
                    logger.exception(
                        "scan_failed request_id=%s "
                        "category=normalized_image_storage",
                        correlation_id,
                    )
                    raise

                logger.info(
                    "scan_stage=normalized_image_storage_completed "
                    "request_id=%s encode_ms=%.2f storage_ms=%.2f",
                    correlation_id,
                    encode_elapsed_ms,
                    (perf_counter() - storage_started) * 1000,
                )

        # STEP 5: Preserve the existing response contract.
        pipeline_dict["processed_image_url"] = processed_url

        logger.info(
            "scan_stage=cv_service_completed request_id=%s "
            "total_elapsed_ms=%.2f",
            correlation_id,
            (perf_counter() - total_started) * 1000,
        )

        return pipeline_dict


# Shared service instance.
cv_service = CVService()
