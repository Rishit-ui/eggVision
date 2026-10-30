"""Non-ML candidate-contour screening for capture-quality review.

This module deliberately does *not* identify eggs. It screens isolated,
egg-like foreground candidates so optical measurements can use a likely subject
rather than the entire frame. A candidate is never evidence of egg identity.
"""

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class ScreeningThresholds:
    """Image-space capture gates, not learned egg-likelihood parameters."""

    min_area_fraction: float = 0.02
    max_area_fraction: float = 0.75
    min_aspect_ratio: float = 1.05
    max_aspect_ratio: float = 2.4
    min_solidity: float = 0.80
    dark_background_luminance: int = 75
    light_background_luminance: int = 190
    background_difference: int = 18
    canny_low: int = 35
    canny_high: int = 110
    morphology_kernel_px: int = 9
    duplicate_iou: float = 0.55
    multiple_candidate_fraction: float = 0.35


@dataclass
class DetectionResult:
    """Output of a non-validated candidate-contour screen."""

    found: bool
    bbox: tuple[int, int, int, int] | None = None
    confidence: float | None = None  # Always None: this is not a model score.
    egg_count: int = 0  # Backwards-compatible name for candidate count.
    contour: np.ndarray | None = None
    candidate_mask: np.ndarray | None = None
    message: str | None = None
    status: str = "UNCERTAIN"
    capture_mode: str = "general_photograph"
    algorithm: str = "opencv_candidate_contour_screen_v2"


class EggDetector:
    """Screen isolated candidates in dark-candling and general-photo captures."""

    def __init__(self, thresholds: ScreeningThresholds | None = None):
        self.thresholds = thresholds or ScreeningThresholds()

    def _capture_mode(self, gray: np.ndarray) -> str:
        border = np.concatenate((gray[0], gray[-1], gray[:, 0], gray[:, -1]))
        return "controlled_candling" if float(np.median(border)) <= self.thresholds.dark_background_luminance else "general_photograph"

    @staticmethod
    def _bbox_iou(first: tuple[int, int, int, int], second: tuple[int, int, int, int]) -> float:
        ax, ay, aw, ah = first
        bx, by, bw, bh = second
        left, top = max(ax, bx), max(ay, by)
        right, bottom = min(ax + aw, bx + bw), min(ay + ah, by + bh)
        intersection = max(0, right - left) * max(0, bottom - top)
        union = aw * ah + bw * bh - intersection
        return intersection / union if union else 0.0

    def _candidate_masks(self, image_bgr: np.ndarray, gray: np.ndarray, mode: str) -> list[np.ndarray]:
        """Build complementary foreground proposals without assuming background colour."""
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        kernel_size = self.thresholds.morphology_kernel_px | 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        masks: list[np.ndarray] = []

        if mode == "controlled_candling":
            _, otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            masks.append(otsu)

        lab_u8 = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
        border_u8 = np.concatenate((lab_u8[0], lab_u8[-1], lab_u8[:, 0], lab_u8[:, -1]), axis=0)
        bg_f32 = np.median(border_u8, axis=0).astype(np.float32)

        thresh_sq = float(self.thresholds.background_difference ** 2)
        # Memory-efficient channel-by-channel sum of squared differences avoids
        # allocating 800+ MB float64/int16 distance buffers on large images.
        diff_l = lab_u8[:, :, 0].astype(np.float32) - bg_f32[0]
        dist_sq = diff_l * diff_l
        del diff_l

        diff_a = lab_u8[:, :, 1].astype(np.float32) - bg_f32[1]
        dist_sq += diff_a * diff_a
        del diff_a

        diff_b = lab_u8[:, :, 2].astype(np.float32) - bg_f32[2]
        dist_sq += diff_b * diff_b
        del diff_b
        del lab_u8

        masks.append((dist_sq >= thresh_sq).astype(np.uint8) * 255)
        del dist_sq

        # Fallback for white-on-white scenes where only shell edges are visible.
        edges = cv2.Canny(blurred, self.thresholds.canny_low, self.thresholds.canny_high)
        masks.append(cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2))
        return [cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1) for mask in masks]

    def _valid_candidates(self, masks: list[np.ndarray], image_shape: tuple[int, int]) -> list[dict]:
        h, w = image_shape
        total_area = float(h * w)
        candidates: list[dict] = []
        for mask in masks:
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                area = float(cv2.contourArea(contour))
                fraction = area / total_area
                if not self.thresholds.min_area_fraction <= fraction <= self.thresholds.max_area_fraction:
                    continue
                x, y, cw, ch = cv2.boundingRect(contour)
                aspect = max(cw, ch) / max(1, min(cw, ch))
                hull_area = float(cv2.contourArea(cv2.convexHull(contour)))
                solidity = area / max(1.0, hull_area)
                if not self.thresholds.min_aspect_ratio <= aspect <= self.thresholds.max_aspect_ratio or solidity < self.thresholds.min_solidity:
                    continue
                candidate = {"contour": contour, "area": area, "bbox": (x, y, cw, ch)}
                if all(self._bbox_iou(candidate["bbox"], previous["bbox"]) < self.thresholds.duplicate_iou for previous in candidates):
                    candidates.append(candidate)
        return sorted(candidates, key=lambda candidate: candidate["area"], reverse=True)

    def detect(self, image_bgr: np.ndarray) -> DetectionResult:
        if image_bgr is None or image_bgr.size == 0:
            return DetectionResult(False, status="INVALID_IMAGE", message="The image could not be decoded.")
        if image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
            return DetectionResult(False, status="INVALID_IMAGE", message="Expected a three-channel colour image.")

        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        mode = self._capture_mode(gray)
        candidates = self._valid_candidates(self._candidate_masks(image_bgr, gray, mode), gray.shape)
        if not candidates:
            border = np.concatenate((gray[0], gray[-1], gray[:, 0], gray[:, -1]))
            unsupported = float(np.std(border)) < 8.0 and float(np.median(border)) >= self.thresholds.light_background_luminance
            status = "UNSUPPORTED_BACKGROUND" if unsupported else "NO_CANDIDATE_CONTOUR"
            message = (
                "The bright, uniform background does not provide a reliable subject boundary. Use a contrasting matte background or controlled chamber."
                if unsupported else "No isolated candidate contour could be screened. This does not determine whether an egg is present."
            )
            return DetectionResult(False, status=status, capture_mode=mode, message=message)

        best = candidates[0]
        mask = np.zeros(gray.shape, dtype=np.uint8)
        cv2.drawContours(mask, [best["contour"]], -1, 255, thickness=cv2.FILLED)
        multiple = len(candidates) > 1 and candidates[1]["area"] >= best["area"] * self.thresholds.multiple_candidate_fraction
        if multiple:
            return DetectionResult(True, best["bbox"], egg_count=len(candidates), contour=best["contour"], candidate_mask=mask, status="MULTIPLE_CANDIDATES", capture_mode=mode, message="Multiple isolated candidates were screened; capture one subject at a time. No egg identity was established.")
        return DetectionResult(True, best["bbox"], egg_count=1, contour=best["contour"], candidate_mask=mask, status="UNCERTAIN", capture_mode=mode, message="One isolated candidate contour was screened. This is not a trained egg-detection result.")
