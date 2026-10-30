"""
CV Service for Backend Pipeline Integration.

Decodes incoming image uploads, executes VisionPipeline,
and generates processed/normalized image artifacts for storage.
Protected with memory bounds, bounded working resolution, and concurrency limits.
"""

import asyncio
import gc
import logging
import uuid
from time import perf_counter
from typing import Any

import cv2
import numpy as np

from ml.vision.pipeline import PipelineResult, VisionPipeline
from app.services.storage_service import storage_service


logger = logging.getLogger(__name__)

# Max working dimension for the CV screening pipeline.
# Keeps peak memory well below Render's 512 MB ceiling while preserving full detail.
MAX_WORKING_DIM = 1600


def _decode_and_bound_image(
    image_bytes: bytes,
    max_dimension: int = MAX_WORKING_DIM,
) -> tuple[np.ndarray | None, int, int, float]:
    """
    Synchronous image decode and bounded working image preparation.
    Runs in a worker thread to keep the event loop free.
    Returns: (working_image_bgr, original_width, original_height, scale_factor)
    """
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image_bgr = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    del image_array

    if image_bgr is None:
        return None, 0, 0, 1.0

    orig_h, orig_w = image_bgr.shape[:2]
    max_edge = max(orig_h, orig_w)

    if max_edge > max_dimension:
        scale = max_dimension / float(max_edge)
        new_w = max(1, int(round(orig_w * scale)))
        new_h = max(1, int(round(orig_h * scale)))
        working_bgr = cv2.resize(
            image_bgr,
            (new_w, new_h),
            interpolation=cv2.INTER_AREA,
        )
        del image_bgr
        return working_bgr, orig_w, orig_h, scale

    return image_bgr, orig_w, orig_h, 1.0


class CVService:
    """Connects FastAPI scan requests with the vision pipeline."""

    def __init__(self, max_concurrent_processing: int = 1) -> None:
        self.pipeline = VisionPipeline()

        # Limit simultaneous CV operations to protect low-resource deployment instances.
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
        The original image is stored by the caller.
        All heavy memory allocations are protected by the processing semaphore.
        """
        total_started = perf_counter()

        async with self._processing_semaphore:
            # STEP 1: Decode image inside semaphore without blocking event loop
            decode_started = perf_counter()

            try:
                working_bgr, orig_w, orig_h, scale = await asyncio.to_thread(
                    _decode_and_bound_image,
                    image_bytes,
                    MAX_WORKING_DIM,
                )
            except Exception:
                logger.exception(
                    "scan_failed request_id=%s category=image_decode",
                    correlation_id,
                )
                raise

            # Handle invalid image data
            if working_bgr is None:
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
                        "The uploaded file could not be parsed as a valid image."
                    ),
                    "processed_image_url": None,
                    "geometry": None,
                    "candidate_geometry": None,
                    "analysis": {
                        "status": "INVALID_IMAGE",
                        "model": None,
                        "detections": [],
                        "limitations": [
                            "The uploaded bytes could not be decoded as an image."
                        ],
                        "message": "Invalid image data.",
                    },
                    "can_proceed_to_inference": False,
                }

            work_h, work_w = working_bgr.shape[:2]
            logger.info(
                "scan_stage=image_decoded request_id=%s "
                "elapsed_ms=%.2f orig_w=%d orig_h=%d work_w=%d work_h=%d scale=%.4f",
                correlation_id,
                (perf_counter() - decode_started) * 1000,
                orig_w,
                orig_h,
                work_w,
                work_h,
                scale,
            )

            # STEP 2: Execute synchronous CV pipeline in worker thread
            cv_started = perf_counter()
            logger.info(
                "scan_stage=cv_processing_started request_id=%s",
                correlation_id,
            )

            try:
                result: PipelineResult = await asyncio.to_thread(
                    self.pipeline.process,
                    working_bgr,
                )
            except Exception:
                logger.exception(
                    "scan_failed request_id=%s category=cv_processing",
                    correlation_id,
                )
                raise
            finally:
                del working_bgr

            logger.info(
                "scan_stage=cv_processing_completed request_id=%s elapsed_ms=%.2f",
                correlation_id,
                (perf_counter() - cv_started) * 1000,
            )

            # STEP 3: Convert pipeline output and rescale geometry if downscaled
            try:
                pipeline_dict = result.to_dict()
            except Exception:
                logger.exception(
                    "scan_failed request_id=%s category=result_serialization",
                    correlation_id,
                )
                raise

            # Rescale candidate geometry back to original coordinates
            if pipeline_dict.get("candidate_geometry") and scale < 1.0:
                geo = pipeline_dict["candidate_geometry"]
                geo["width"] = round(geo["width"] / scale, 2)
                geo["height"] = round(geo["height"] / scale, 2)
                geo["area"] = round(geo["area"] / (scale * scale), 2)
                geo["centroid"] = [
                    round(geo["centroid"][0] / scale, 2),
                    round(geo["centroid"][1] / scale, 2),
                ]

            # Preserve both original and working resolution in metrics
            if "metrics" in pipeline_dict and isinstance(pipeline_dict["metrics"], dict):
                pipeline_dict["metrics"]["resolution"] = f"{orig_w}x{orig_h}"
                if scale < 1.0:
                    pipeline_dict["metrics"]["working_resolution"] = f"{work_w}x{work_h}"
                    pipeline_dict["metrics"]["scale_factor"] = round(scale, 4)

            # STEP 4: Upload normalized image when available
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
                        [cv2.IMWRITE_JPEG_QUALITY, 90],
                    )
                except Exception:
                    logger.exception(
                        "scan_failed request_id=%s category=normalized_image_encoding",
                        correlation_id,
                    )
                    raise

                encode_elapsed_ms = (perf_counter() - encode_started) * 1000

                if not success:
                    logger.warning(
                        "scan_warning request_id=%s category=normalized_image_encoding_failed",
                        correlation_id,
                    )
                else:
                    encoded_bytes = encoded_buffer.tobytes()
                    del encoded_buffer
                    normalized_filename = f"normalized_{uuid.uuid4()}.jpg"
                    storage_started = perf_counter()

                    try:
                        processed_url = await storage_service.upload_image(
                            encoded_bytes,
                            normalized_filename,
                            "image/jpeg",
                        )
                    except Exception:
                        logger.exception(
                            "scan_failed request_id=%s category=normalized_image_storage",
                            correlation_id,
                        )
                        raise
                    finally:
                        del encoded_bytes

                    logger.info(
                        "scan_stage=normalized_image_storage_completed "
                        "request_id=%s encode_ms=%.2f storage_ms=%.2f",
                        correlation_id,
                        encode_elapsed_ms,
                        (perf_counter() - storage_started) * 1000,
                    )

            # STEP 5: Preserve the existing response contract
            pipeline_dict["processed_image_url"] = processed_url

            # Force immediate garbage collection to release working memory to OS
            gc.collect()

            logger.info(
                "scan_stage=cv_service_completed request_id=%s total_elapsed_ms=%.2f",
                correlation_id,
                (perf_counter() - total_started) * 1000,
            )

            return pipeline_dict


# Shared service instance.
cv_service = CVService()
