"""Egg Image Normalization Module.

Applies geometric alignment, canonical resizing, background masking,
and optical contrast normalization while preserving internal biological signals.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import cv2
import numpy as np
from .segmentation import EggGeometry


@dataclass
class NormalizationResult:
    """Output from the EggNormalizer."""
    normalized_image: np.ndarray  # Canonical 512x512 BGR image
    normalized_mask: np.ndarray   # Canonical 512x512 binary mask
    clahe_image: np.ndarray        # CLAHE enhanced 512x512 image
    rotation_angle_applied: float
    canonical_size: Tuple[int, int]
    success: bool
    error: Optional[str] = None


class EggNormalizer:
    """Normalizes candling images into standard geometry and optical range."""

    def __init__(self, target_size: int = 512, clahe_clip_limit: float = 2.0, clahe_tile_grid: int = 8):
        self.target_size = target_size
        self.clahe_clip_limit = clahe_clip_limit
        self.clahe_tile_grid = (clahe_tile_grid, clahe_tile_grid)

    def normalize(
        self,
        image_bgr: np.ndarray,
        mask: np.ndarray,
        geometry: EggGeometry,
        align_vertical: bool = True
    ) -> NormalizationResult:
        """Run normalization pipeline."""
        if image_bgr is None or mask is None:
            empty = np.zeros((self.target_size, self.target_size, 3), dtype=np.uint8)
            return NormalizationResult(
                normalized_image=empty,
                normalized_mask=np.zeros((self.target_size, self.target_size), dtype=np.uint8),
                clahe_image=empty,
                rotation_angle_applied=0.0,
                canonical_size=(self.target_size, self.target_size),
                success=False,
                error="Null input passed to normalizer."
            )

        h, w = image_bgr.shape[:2]

        # 1. Mask out exterior enclosure/chamber noise
        masked_bgr = cv2.bitwise_and(image_bgr, image_bgr, mask=mask)

        # 2. Rotation alignment: Orient major axis vertically
        rotation_angle = 0.0
        if align_vertical and geometry.orientation_deg is not None:
            # Orientation deg: angle of major axis from vertical
            # Rotate so that angle becomes 0 (or 180)
            angle = geometry.orientation_deg
            # OpenCV angle: if near 90 or 270, it is horizontal; if near 0 or 180, already vertical
            if abs(angle - 0) > 3.0 and abs(angle - 180) > 3.0:
                # Rotate around centroid
                cx, cy = geometry.centroid_x, geometry.centroid_y
                # If angle > 90, rotate by (180 - angle), else by -angle
                rotation_angle = float(180.0 - angle if angle > 90.0 else -angle)
                M = cv2.getRotationMatrix2D((cx, cy), rotation_angle, 1.0)
                masked_bgr = cv2.warpAffine(masked_bgr, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))
                mask = cv2.warpAffine(mask, M, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)

        # 3. Crop tightly to rotated egg mask bounding box
        coords = cv2.findNonZero(mask)
        if coords is not None:
            rx, ry, rw, rh = cv2.boundingRect(coords)
            # Add small padding buffer (4%)
            pad_x = int(rw * 0.04)
            pad_y = int(rh * 0.04)
            x1 = max(0, rx - pad_x)
            y1 = max(0, ry - pad_y)
            x2 = min(w, rx + rw + pad_x)
            y2 = min(h, ry + rh + pad_y)

            cropped_img = masked_bgr[y1:y2, x1:x2]
            cropped_mask = mask[y1:y2, x1:x2]
        else:
            cropped_img = masked_bgr
            cropped_mask = mask

        # 4. Canonical aspect-preserving resize with letterbox padding into (target_size, target_size)
        ch, cw = cropped_img.shape[:2]
        if ch > 0 and cw > 0:
            scale = min((self.target_size - 16) / ch, (self.target_size - 16) / cw)
            new_w = max(1, int(cw * scale))
            new_h = max(1, int(ch * scale))

            resized_img = cv2.resize(cropped_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
            resized_mask = cv2.resize(cropped_mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)

            canvas_img = np.zeros((self.target_size, self.target_size, 3), dtype=np.uint8)
            canvas_mask = np.zeros((self.target_size, self.target_size), dtype=np.uint8)

            start_y = (self.target_size - new_h) // 2
            start_x = (self.target_size - new_w) // 2

            canvas_img[start_y:start_y + new_h, start_x:start_x + new_w] = resized_img
            canvas_mask[start_y:start_y + new_h, start_x:start_x + new_w] = resized_mask
        else:
            canvas_img = cv2.resize(masked_bgr, (self.target_size, self.target_size))
            canvas_mask = cv2.resize(mask, (self.target_size, self.target_size))

        # 5. CLAHE (Contrast Limited Adaptive Histogram Equalization) on LAB L-channel
        lab = cv2.cvtColor(canvas_img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=self.clahe_clip_limit, tileGridSize=self.clahe_tile_grid)
        # Apply CLAHE only inside egg mask to preserve black background
        l_clahe = clahe.apply(l)
        l_final = np.where(canvas_mask > 0, l_clahe, 0)
        lab_clahe = cv2.merge((l_final, a, b))
        clahe_bgr = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)

        return NormalizationResult(
            normalized_image=canvas_img,
            normalized_mask=canvas_mask,
            clahe_image=clahe_bgr,
            rotation_angle_applied=round(rotation_angle, 2),
            canonical_size=(self.target_size, self.target_size),
            success=True
        )
