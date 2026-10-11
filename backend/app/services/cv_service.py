"""CV Service for Backend Pipeline Integration.

Decodes incoming raw image uploads, executes VisionPipeline,
and generates processed/normalized image artifacts for storage.
"""

import uuid
from typing import Optional, Dict, Any, Tuple
import cv2
import numpy as np

from ml.vision.pipeline import VisionPipeline, PipelineResult
from app.services.storage_service import storage_service


class CVService:
    """Service bridge connecting FastAPI endpoints with the ML vision pipeline."""

    def __init__(self):
        self.pipeline = VisionPipeline()

    async def process_scan_image(self, image_bytes: bytes, original_filename: str) -> Dict[str, Any]:
        """Decode image bytes, run CV quality and normalization, and upload processed image.
        
        Returns:
            Dictionary containing:
            - image_quality: "GOOD" | "ACCEPTABLE" | "POOR"
            - quality_score: float
            - warnings: list[str]
            - retake_recommended: bool
            - recommendation: Optional[str]
            - processed_image_url: Optional[str]
            - geometry: Optional[dict]
            - can_proceed_to_inference: bool
        """
        # Decode byte buffer into OpenCV BGR numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        image_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image_bgr is None:
            return {
                "image_quality": "POOR",
                "quality_score": 0.0,
                "warnings": ["INVALID_IMAGE_DATA"],
                "retake_recommended": True,
                "recommendation": "The uploaded file could not be parsed as a valid image.",
                "processed_image_url": None,
                "geometry": None,
                "can_proceed_to_inference": False
            }

        # Run computer vision pipeline
        result: PipelineResult = self.pipeline.process(image_bgr)
        pipeline_dict = result.to_dict()

        processed_url = None
        if result.normalization and result.normalization.success:
            # Encode canonical normalized image to JPEG
            norm_img = result.normalization.normalized_image
            success, encoded_buf = cv2.imencode(".jpg", norm_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            if success:
                norm_filename = f"normalized_{uuid.uuid4()}.jpg"
                processed_url = await storage_service.upload_image(
                    encoded_buf.tobytes(),
                    norm_filename,
                    "image/jpeg"
                )

        pipeline_dict["processed_image_url"] = processed_url
        return pipeline_dict


cv_service = CVService()
