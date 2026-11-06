"""Abstract inference engine interface for EggVision AI."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np


@dataclass
class PredictionResult:
    """Result from the inference engine."""
    status: str  # 'completed', 'model_not_ready', 'error'
    freshness_class: str | None = None
    freshness_score: float | None = None
    estimated_age_min: int | None = None
    estimated_age_max: int | None = None
    predicted_haugh_unit: float | None = None
    confidence: float | None = None
    air_cell_area: float | None = None
    air_cell_ratio: float | None = None
    yolk_visibility: str | None = None
    crack_probability: float | None = None
    blood_spot_probability: float | None = None
    explanation: list[str] = field(default_factory=list)
    heatmap: np.ndarray | None = None
    inference_time_ms: float | None = None
    model_version: str | None = None
    error_message: str | None = None


@dataclass
class ModelInfo:
    """Information about the loaded model."""
    version: str
    model_type: str
    is_ready: bool
    description: str
    dataset_version: str | None = None
    metrics: dict | None = None
    trained_at: datetime | None = None


class InferenceEngine(ABC):
    """Abstract base class for egg freshness inference engines.
    
    All inference engines must implement this interface.
    This allows swapping models without changing the rest of the system.
    """

    @abstractmethod
    async def predict(self, image: np.ndarray, metadata: dict | None = None) -> PredictionResult:
        """Run inference on an egg image.
        
        Args:
            image: Preprocessed egg image as numpy array (H, W, C) in BGR format.
            metadata: Optional metadata dict with keys like 'temperature', 'humidity',
                     'egg_type', 'storage_condition'.
        
        Returns:
            PredictionResult with freshness prediction and supporting data.
        """
        ...

    @abstractmethod
    def get_model_info(self) -> ModelInfo:
        """Return information about the currently loaded model."""
        ...

    @abstractmethod
    def is_ready(self) -> bool:
        """Check if the model is loaded and ready for inference."""
        ...
