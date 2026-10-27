"""Placeholder inference engine that returns MODEL_NOT_READY.

This is used when no trained model is available.
It ensures the system architecture is complete and the API
returns honest status instead of fake predictions.
"""

import numpy as np

from .engine import InferenceEngine, ModelInfo, PredictionResult


class PlaceholderEngine(InferenceEngine):
    """Placeholder engine that always returns MODEL_NOT_READY.
    
    This engine is used during development before a real model
    is trained and validated. It does NOT generate fake predictions.
    """

    async def predict(self, image: np.ndarray, metadata: dict | None = None) -> PredictionResult:
        """Return MODEL_NOT_READY status. No fake predictions."""
        return PredictionResult(
            status="model_not_ready",
            error_message="No trained model is currently loaded. "
                         "The system architecture is ready for model integration. "
                         "Please train and deploy a model to enable predictions.",
            model_version="none",
        )

    def get_model_info(self) -> ModelInfo:
        """Return info indicating no model is loaded."""
        return ModelInfo(
            version="none",
            model_type="placeholder",
            is_ready=False,
            description="No trained model loaded. The inference pipeline is ready "
                       "for model integration once training is complete.",
        )

    def is_ready(self) -> bool:
        """Placeholder is never ready for real inference."""
        return False
