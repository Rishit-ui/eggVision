"""Egg Segmentation Module for Candling and Exterior Images.

Extracts pixel-level binary egg mask, suppresses cast shadows and background
glare, validates mask morphometry, and computes geometric features including
area, axes, centroid, aspect ratio, solidity, perimeter, and major-axis orientation.
"""

from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
import cv2
import numpy as np


@dataclass
class EggGeometry:
    """Morphometric measurements of the segmented candidate egg."""
    area: float
    width: float
    height: float
    aspect_ratio: float
    centroid_x: float
    centroid_y: float
    orientation_deg: float  # Angle of major axis relative to vertical (0 = vertical)
    fitted_ellipse_center: Optional[Tuple[float, float]] = None
    fitted_ellipse_axes: Optional[Tuple[float, float]] = None
    solidity: float = 1.0
    perimeter: float = 0.0
    eccentricity: float = 0.0
    segmentation_status: str = "VALID_CANDIDATE"


@dataclass
class SegmentationResult:
    """Output containing pixel mask, contour, and geometry."""
    mask: np.ndarray  # Binary mask (uint8 0 or 255)
    contour: np.ndarray
    geometry: EggGeometry
    success: bool
    status: str = "VALID_CANDIDATE"  # VALID_CANDIDATE, SEGMENTATION_UNCERTAIN, NO_SUBJECT
    confidence_score: Optional[float] = None
    error: Optional[str] = None


class EggSegmenter:
    """Extracts precise pixel-level egg mask and morphometric attributes."""

    def __init__(self, min_solidity: float = 0.82, max_aspect_ratio: float = 2.4):
        self.min_solidity = min_solidity
        self.max_aspect_ratio = max_aspect_ratio

    def _suppress_shadows_and_glare(
        self,
        image_bgr: np.ndarray,
        initial_mask: np.ndarray,
        cnt: np.ndarray,
    ) -> np.ndarray:
        """
        Refine the candidate mask by removing cast shadows or attached table glare
        that deviate in color from the core egg shell.
        """
        h, w = image_bgr.shape[:2]
        if len(cnt) < 5:
            return initial_mask

        # Fit ellipse to candidate contour
        try:
            ellipse = cv2.fitEllipse(cnt)
            (ecx, ecy), (d1, d2), angle = ellipse
        except cv2.error:
            return initial_mask

        # Sample shell color in the central 40% of the fitted ellipse
        core_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.ellipse(
            core_mask,
            (int(round(ecx)), int(round(ecy))),
            (max(1, int(round(d1 * 0.20))), max(1, int(round(d2 * 0.20)))),
            angle,
            0,
            360,
            255,
            -1,
        )

        core_pixels = image_bgr[core_mask > 0]
        if core_pixels.size == 0:
            return initial_mask

        lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
        core_lab = cv2.cvtColor(core_pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2LAB).astype(np.float32)
        shell_med_lab = np.median(core_lab.reshape(-1, 3), axis=0)

        # Difference in LAB color from core shell
        color_diff = np.linalg.norm(lab - shell_med_lab, axis=2)

        # Allow generous variance for natural shell shading (up to 75 LAB units)
        # but prune extreme outliers (> 90 units, e.g. bright white glare on dark background
        # or dark shadows on light background)
        color_valid = (color_diff < 90.0)

        # Geometric envelope: points must lie within 1.15x of fitted ellipse
        envelope_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.ellipse(
            envelope_mask,
            (int(round(ecx)), int(round(ecy))),
            (max(1, int(round(d1 * 0.58))), max(1, int(round(d2 * 0.58)))),
            angle,
            0,
            360,
            255,
            -1,
        )

        # Refined mask: within initial contour AND inside envelope AND matching shell color
        refined = (initial_mask > 0) & (envelope_mask > 0) & color_valid
        refined_u8 = refined.astype(np.uint8) * 255

        # Morphological clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        opened = cv2.morphologyEx(refined_u8, cv2.MORPH_OPEN, kernel)
        closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)

        # Keep largest connected component
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
        if num_labels <= 1:
            return initial_mask

        largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
        largest_area = stats[largest_label, cv2.CC_STAT_AREA]

        # Only accept refined mask if it retains at least 50% of candidate area
        initial_area = np.sum(initial_mask > 0)
        if largest_area >= 0.50 * initial_area:
            return (labels == largest_label).astype(np.uint8) * 255

        return initial_mask

    def segment(self, image_bgr: np.ndarray, contour_hint: Optional[np.ndarray] = None) -> SegmentationResult:
        """Segment intact egg and compute geometric characteristics."""
        if image_bgr is None or image_bgr.size == 0:
            empty_mask = np.zeros((1, 1), dtype=np.uint8)
            return SegmentationResult(
                mask=empty_mask,
                contour=np.array([]),
                geometry=EggGeometry(0, 0, 0, 0, 0, 0, 0, segmentation_status="NO_SUBJECT"),
                success=False,
                status="NO_SUBJECT",
                error="Empty image passed for segmentation."
            )

        h, w = image_bgr.shape[:2]
        raw_mask = np.zeros((h, w), dtype=np.uint8)

        if contour_hint is not None and len(contour_hint) >= 5:
            cnt = contour_hint
            cv2.drawContours(raw_mask, [cnt], -1, 255, thickness=cv2.FILLED)
            # Refine mask to eliminate attached shadows or background glare
            refined_mask = self._suppress_shadows_and_glare(image_bgr, raw_mask, cnt)
            contours, _ = cv2.findContours(refined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                cnt = max(contours, key=cv2.contourArea)
                mask = np.zeros((h, w), dtype=np.uint8)
                cv2.drawContours(mask, [cnt], -1, 255, thickness=cv2.FILLED)
            else:
                mask = raw_mask
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
                    mask=raw_mask,
                    contour=np.array([]),
                    geometry=EggGeometry(0, 0, 0, 0, 0, 0, 0, segmentation_status="NO_SUBJECT"),
                    success=False,
                    status="NO_SUBJECT",
                    error="Unable to extract egg contour."
                )
            cnt = max(contours, key=cv2.contourArea)
            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(mask, [cnt], -1, 255, thickness=cv2.FILLED)

        # Compute Moments for centroid
        M = cv2.moments(cnt)
        if M["m00"] > 0:
            cx = float(M["m10"] / M["m00"])
            cy = float(M["m01"] / M["m00"])
        else:
            cx, cy = float(w / 2), float(h / 2)

        area = float(cv2.contourArea(cnt))
        perimeter = float(cv2.arcLength(cnt, True))
        x, y, bw, bh = cv2.boundingRect(cnt)

        # Solidity: contour area / convex hull area
        hull = cv2.convexHull(cnt)
        hull_area = float(cv2.contourArea(hull))
        solidity = float(area / max(1.0, hull_area))

        # Fit ellipse for orientation and fine axes (requires >= 5 points)
        eccentricity = 0.0
        if len(cnt) >= 5:
            try:
                ellipse = cv2.fitEllipse(cnt)
                (ecx, ecy), (d1, d2), angle = ellipse
                major_axis = max(d1, d2)
                minor_axis = max(1.0, min(d1, d2))
                aspect_ratio = float(major_axis / minor_axis)
                orientation_deg = float(angle if d2 >= d1 else (angle + 90) % 180)
                ellipse_center = (round(float(ecx), 2), round(float(ecy), 2))
                ellipse_axes = (round(float(major_axis), 2), round(float(minor_axis), 2))
                # Eccentricity: sqrt(1 - (b/a)^2)
                eccentricity = float(np.sqrt(max(0.0, 1.0 - (minor_axis / max(1.0, major_axis)) ** 2)))
            except cv2.error:
                major_axis = float(max(bw, bh))
                minor_axis = float(max(1, min(bw, bh)))
                aspect_ratio = float(major_axis / minor_axis)
                orientation_deg = 0.0
                ellipse_center = (cx, cy)
                ellipse_axes = (major_axis, minor_axis)
        else:
            major_axis = float(max(bw, bh))
            minor_axis = float(max(1, min(bw, bh)))
            aspect_ratio = float(major_axis / minor_axis)
            orientation_deg = 0.0
            ellipse_center = (cx, cy)
            ellipse_axes = (major_axis, minor_axis)

        # Status validation: Egg silhouettes have high solidity (> 0.82) and natural aspect ratio (1.05 - 2.4)
        is_valid = (solidity >= self.min_solidity) and (1.05 <= aspect_ratio <= self.max_aspect_ratio) and (area > 3000)
        status = "VALID_CANDIDATE" if is_valid else "SEGMENTATION_UNCERTAIN"

        geometry = EggGeometry(
            area=round(area, 1),
            width=round(float(bw), 1),
            height=round(float(bh), 1),
            aspect_ratio=round(aspect_ratio, 3),
            centroid_x=round(cx, 1),
            centroid_y=round(cy, 1),
            orientation_deg=round(orientation_deg, 2),
            fitted_ellipse_center=ellipse_center,
            fitted_ellipse_axes=ellipse_axes,
            solidity=round(solidity, 3),
            perimeter=round(perimeter, 1),
            eccentricity=round(eccentricity, 3),
            segmentation_status=status,
        )

        return SegmentationResult(
            mask=mask,
            contour=cnt,
            geometry=geometry,
            success=True,
            status=status,
            confidence_score=round(solidity, 2) if is_valid else 0.5,
        )
