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
        that deviate in color or geometry from the core egg shell.
        """
        h, w = image_bgr.shape[:2]
        coords = np.where(initial_mask > 0)
        n_pixels = len(coords[0])
        if n_pixels < 1500:
            return initial_mask

        # Step 1: Color clustering (LAB 2-cluster separation)
        # Identifies and separates severe bimodal color contamination (e.g. white glare
        # or dark shadow fused with brown or cream egg shell).
        lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
        features = lab[coords].astype(np.float32)

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels, centers = cv2.kmeans(features, 2, None, criteria, 5, cv2.KMEANS_PP_CENTERS)
        cluster_dist = float(np.linalg.norm(centers[0] - centers[1]))

        working_mask = initial_mask.copy()
        if cluster_dist >= 40.0:
            # Significant color bifurcation inside candidate: separate clusters
            c0_mask = np.zeros((h, w), dtype=np.uint8)
            c0_mask[coords] = (labels.flatten() == 0).astype(np.uint8) * 255
            c1_mask = np.zeros((h, w), dtype=np.uint8)
            c1_mask[coords] = (labels.flatten() == 1).astype(np.uint8) * 255

            def _score_component(m: np.ndarray) -> tuple[float, Optional[np.ndarray]]:
                cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if not cnts:
                    return 0.0, None
                best = max(cnts, key=cv2.contourArea)
                area = cv2.contourArea(best)
                if area < 1500:
                    return 0.0, None
                hull = cv2.convexHull(best)
                sol = area / max(1.0, cv2.contourArea(hull))
                bx, by, bw, bh = cv2.boundingRect(best)
                asp = max(bw, bh) / max(1, min(bw, bh))
                shape_fit = (1.2 if sol >= 0.88 else 0.4) * (1.2 if 1.1 <= asp <= 2.2 else 0.4)
                cx, cy = bx + bw / 2.0, by + bh / 2.0
                centrality = 1.0 - min(1.0, np.hypot(cx - w / 2.0, cy - h / 2.0) / (0.7 * np.hypot(w, h)))
                return area * shape_fit * (1.0 + centrality), best

            score0, best0 = _score_component(c0_mask)
            score1, best1 = _score_component(c1_mask)

            chosen_cnt = best0 if score0 >= score1 else best1
            if chosen_cnt is not None:
                isolated = np.zeros((h, w), dtype=np.uint8)
                cv2.drawContours(isolated, [chosen_cnt], -1, 255, -1)
                kernel_c = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                isolated = cv2.morphologyEx(isolated, cv2.MORPH_CLOSE, kernel_c)
                working_mask = isolated
                # Re-extract contour from isolated component
                cnts_iso, _ = cv2.findContours(working_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if cnts_iso:
                    cnt = max(cnts_iso, key=cv2.contourArea)

        # Step 2: Elliptical Envelope & Convex Residual Pruning
        if len(cnt) >= 5:
            try:
                ellipse = cv2.fitEllipse(cnt)
                (ecx, ecy), (d1, d2), angle = ellipse
                envelope_mask = np.zeros((h, w), dtype=np.uint8)
                cv2.ellipse(
                    envelope_mask,
                    (int(round(ecx)), int(round(ecy))),
                    (max(1, int(round(d1 * 0.56))), max(1, int(round(d2 * 0.56)))),
                    angle,
                    0,
                    360,
                    255,
                    -1,
                )
                trimmed = cv2.bitwise_and(working_mask, envelope_mask)
                cnts_trim, _ = cv2.findContours(trimmed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if cnts_trim:
                    largest_trim = max(cnts_trim, key=cv2.contourArea)
                    if cv2.contourArea(largest_trim) >= 0.55 * np.sum(working_mask > 0):
                        final_clean = np.zeros((h, w), dtype=np.uint8)
                        cv2.drawContours(final_clean, [largest_trim], -1, 255, -1)
                        return final_clean
            except cv2.error:
                pass

        return working_mask

    def segment(self, image_bgr: np.ndarray, contour_hint: Optional[np.ndarray] = None) -> SegmentationResult:
        """Segment intact egg and compute geometric characteristics with validation."""
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

        # Mask Quality Validation:
        # 1. Solidity must be >= 0.82 (smooth convex egg outline)
        # 2. Aspect ratio must be within organic limits [1.05, 2.4]
        # 3. Sufficient pixel area (> 3,000 px)
        # 4. Extent (area / bbox area) between 0.60 and 0.88 (ellipse extent is pi/4 = 0.785)
        extent = area / max(1.0, float(bw * bh))
        is_valid = (
            (solidity >= self.min_solidity)
            and (1.05 <= aspect_ratio <= self.max_aspect_ratio)
            and (area >= 3000.0)
            and (0.55 <= extent <= 0.90)
        )
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
