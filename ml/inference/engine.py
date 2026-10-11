"""Abstract inference engine interface for EggVision AI."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np


@dataclass
class PredictionResult:
    """Result from the inference engine."""
    status: str  # 'completed', 'model_not_ready', 'error'
    freshness_class: Optional[str] = None
    freshness_score: Optional[float] = None
    estimated_age_min: Optional[int] = None
    estimated_age_max: Optional[int] = None
    predicted_haugh_unit: Optional[float] = None
    confidence: Optional[float] = None
    air_cell_area: Optional[float] = None
    air_cell_ratio: Optional[float] = None
    yolk_visibility: Optional[str] = None
    crack_probability: Optional[float] = None
    blood_spot_probability: Optional[float] = None
    explanation: list[str] = field(default_factory=list)
    heatmap: Optional[np.ndarray] = None
    inference_time_ms: Optional[float] = None
    model_version: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class ModelInfo:
    """Information about the loaded model."""
    version: str
    model_type: str
    is_ready: bool
    description: str
    dataset_version: Optional[str] = None
    metrics: Optional[dict] = None
    trained_at: Optional[datetime] = None


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
