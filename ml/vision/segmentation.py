"""Egg Segmentation Module for Candling Images.

Extracts pixel-level binary egg mask and computes morphometric features
including area, axes, centroid, aspect ratio, and major-axis orientation.
"""

from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
import cv2
import numpy as np


@dataclass
class EggGeometry:
    """Morphometric measurements of the segmented egg."""
    area: float
    width: float
    height: float
    aspect_ratio: float
    centroid_x: float
    centroid_y: float
    orientation_deg: float  # Angle of major axis relative to vertical (0 = vertical)
    fitted_ellipse_center: Optional[Tuple[float, float]] = None
    fitted_ellipse_axes: Optional[Tuple[float, float]] = None


@dataclass
class SegmentationResult:
    """Output containing pixel mask, contour, and geometry."""
    mask: np.ndarray  # Binary mask (uint8 0 or 255)
    contour: np.ndarray
    geometry: EggGeometry
    success: bool
    error: Optional[str] = None


class EggSegmenter:
    """Extracts precise pixel-level egg mask and biological geometric attributes."""

    def segment(self, image_bgr: np.ndarray, contour_hint: Optional[np.ndarray] = None) -> SegmentationResult:
        """Segment intact egg and compute geometric characteristics."""
        if image_bgr is None or image_bgr.size == 0:
            empty_mask = np.zeros((1, 1), dtype=np.uint8)
            return SegmentationResult(
                mask=empty_mask,
                contour=np.array([]),
                geometry=EggGeometry(0, 0, 0, 0, 0, 0, 0),
                success=False,
                error="Empty image passed for segmentation."
            )

        h, w = image_bgr.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)

        if contour_hint is not None and len(contour_hint) >= 5:
            cnt = contour_hint
        else:
            # Re-extract contour via color thresholding
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (9, 9), 0)
            _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
            cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
            contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return SegmentationResult(
                    mask=mask,
                    contour=np.array([]),
                    geometry=EggGeometry(0, 0, 0, 0, 0, 0, 0),
                    success=False,
                    error="Unable to extract egg contour."
                )
            cnt = max(contours, key=cv2.contourArea)

        # Draw filled contour onto mask
        cv2.drawContours(mask, [cnt], -1, 255, thickness=cv2.FILLED)

        # Compute Moments for centroid
        M = cv2.moments(cnt)
        if M["m00"] > 0:
            cx = float(M["m10"] / M["m00"])
            cy = float(M["m01"] / M["m00"])
        else:
            cx, cy = float(w / 2), float(h / 2)

        area = float(cv2.contourArea(cnt))
        x, y, bw, bh = cv2.boundingRect(cnt)

        # Fit ellipse for orientation and fine axes (requires >= 5 points)
        if len(cnt) >= 5:
            ellipse = cv2.fitEllipse(cnt)
            (ecx, ecy), (d1, d2), angle = ellipse
            major_axis = max(d1, d2)
            minor_axis = max(1.0, min(d1, d2))
            aspect_ratio = float(major_axis / minor_axis)
            
            # Normalizing angle: angle is measured clockwise from top (0 deg is vertical)
            # If major axis is d2, OpenCV angle is angle of d2
            orientation_deg = float(angle if d2 >= d1 else (angle + 90) % 180)
            ellipse_center = (round(float(ecx), 2), round(float(ecy), 2))
            ellipse_axes = (round(float(major_axis), 2), round(float(minor_axis), 2))
        else:
            major_axis = float(max(bw, bh))
            minor_axis = float(max(1, min(bw, bh)))
            aspect_ratio = float(major_axis / minor_axis)
            orientation_deg = 0.0
            ellipse_center = (cx, cy)
            ellipse_axes = (major_axis, minor_axis)

        geometry = EggGeometry(
            area=round(area, 1),
            width=round(float(bw), 1),
            height=round(float(bh), 1),
            aspect_ratio=round(aspect_ratio, 3),
            centroid_x=round(cx, 1),
            centroid_y=round(cy, 1),
            orientation_deg=round(orientation_deg, 2),
            fitted_ellipse_center=ellipse_center,
            fitted_ellipse_axes=ellipse_axes
        )

        return SegmentationResult(
            mask=mask,
            contour=cnt,
            geometry=geometry,
            success=True
        )
