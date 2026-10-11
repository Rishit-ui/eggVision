"""Egg Detection Module for Controlled Candling Enclosure.

Detects intact egg position, bounding box, and count from optical candling images.
"""

from dataclasses import dataclass
from typing import Optional, Tuple, List
import cv2
import numpy as np


@dataclass
class DetectionResult:
    """Output from the EggDetector."""
    found: bool
    bbox: Optional[Tuple[int, int, int, int]] = None  # (x, y, w, h)
    confidence: float = 0.0
    egg_count: int = 0
    contour: Optional[np.ndarray] = None
    message: Optional[str] = None


class EggDetector:
    """Robust OpenCV candling egg detector for chamber-captured imagery."""

    def __init__(
        self,
        min_area_fraction: float = 0.05,
        max_area_fraction: float = 0.90,
        min_aspect_ratio: float = 0.9,
        max_aspect_ratio: float = 2.2,
    ):
        self.min_area_fraction = min_area_fraction
        self.max_area_fraction = max_area_fraction
        self.min_aspect_ratio = min_aspect_ratio
        self.max_aspect_ratio = max_aspect_ratio

    def detect(self, image_bgr: np.ndarray) -> DetectionResult:
        """Detect the egg candidate in the input candling image."""
        if image_bgr is None or image_bgr.size == 0:
            return DetectionResult(found=False, message="Empty image provided.")

        h, w = image_bgr.shape[:2]
        total_area = float(h * w)

        # Convert to LAB color space for luminance-robust separation
        lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
        l_channel, _, _ = cv2.split(lab)

        # Blur slightly to smooth shell texture
        blurred = cv2.GaussianBlur(l_channel, (7, 7), 0)

        # Otsu thresholding to segment glowing egg from dark background
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Morphological closing to seal internal yolk shadows & open small noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
        opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel, iterations=1)

        # Find external contours
        contours, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        valid_candidates = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            area_frac = area / total_area

            if self.min_area_fraction <= area_frac <= self.max_area_fraction:
                x, y, cw, ch = cv2.boundingRect(cnt)
                aspect = max(cw, ch) / max(1, min(cw, ch))
                
                # Candled egg profile check
                hull = cv2.convexHull(cnt)
                hull_area = cv2.contourArea(hull)
                solidity = float(area / max(1.0, hull_area))

                if self.min_aspect_ratio <= aspect <= self.max_aspect_ratio and solidity > 0.82:
                    valid_candidates.append({
                        "contour": cnt,
                        "area": area,
                        "bbox": (x, y, cw, ch),
                        "solidity": solidity,
                        "aspect": aspect
                    })

        if not valid_candidates:
            # Fallback: check if the whole frame is the egg (e.g. tightly cropped)
            mean_lum = np.mean(l_channel)
            if mean_lum > 40:
                # Egg fills almost the entire frame
                return DetectionResult(
                    found=True,
                    bbox=(0, 0, w, h),
                    confidence=0.70,
                    egg_count=1,
                    message="Full frame egg detected."
                )
            return DetectionResult(
                found=False,
                egg_count=0,
                message="No valid egg contour identified in chamber image."
            )

        # Sort candidates by area descending
        valid_candidates.sort(key=lambda c: c["area"], reverse=True)
        egg_count = len(valid_candidates)

        if egg_count > 1:
            # Check if second candidate is substantially sized (multiple eggs in chamber)
            second_area = valid_candidates[1]["area"]
            first_area = valid_candidates[0]["area"]
            if second_area > 0.35 * first_area:
                return DetectionResult(
                    found=True,
                    bbox=valid_candidates[0]["bbox"],
                    confidence=0.65,
                    egg_count=egg_count,
                    contour=valid_candidates[0]["contour"],
                    message="Warning: Multiple egg candidates detected in scanning frame."
                )

        best = valid_candidates[0]
        # Calculate confidence based on solidity and aspect ratio conformity
        confidence = float(np.clip(best["solidity"] * 0.7 + (1.0 - abs(best["aspect"] - 1.35) * 0.25) * 0.3, 0.5, 0.99))
        confidence = round(confidence, 3)

        return DetectionResult(
            found=True,
            bbox=best["bbox"],
            confidence=confidence,
            egg_count=1,
            contour=best["contour"],
            message="Single egg successfully located."
        )
