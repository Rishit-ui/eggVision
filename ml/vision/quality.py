"""Transparent capture-readiness measurements for image acquisition.

Measurements are deterministic engineering gates, not AI confidence or an egg
quality/freshness score. Exposure is intentionally inconclusive without a
screened candidate region.
"""

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np


class QualityWarning:
    BLUR_DETECTED = "BLUR_DETECTED"
    UNDEREXPOSED = "UNDEREXPOSED_CANDIDATE_ROI"
    OVEREXPOSED = "OVEREXPOSED_CANDIDATE_ROI"
    LOW_CONTRAST = "INSUFFICIENT_CANDIDATE_CONTRAST"
    SPECULAR_REFLECTION = "EXCESSIVE_CANDIDATE_GLARE"
    BORDER_CLIPPED = "CANDIDATE_PARTIALLY_VISIBLE_BORDER_CLIPPED"
    LOW_RESOLUTION = "LOW_RESOLUTION"
    STRONG_SHADOWS = "STRONG_CANDIDATE_SHADOWS"
    NO_CANDIDATE = "NO_CANDIDATE_CONTOUR"
    UNSUPPORTED_BACKGROUND = "UNSUPPORTED_BACKGROUND"
    MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATES"
    EXPOSURE_INCONCLUSIVE = "EXPOSURE_ASSESSMENT_INCONCLUSIVE"
    INVALID_IMAGE = "INVALID_IMAGE_DATA"


@dataclass(frozen=True)
class QualityThresholds:
    """Configurable capture gates; not validated egg-quality thresholds."""

    # Calibrated for organic smooth surfaces (egg shell) with edge-gradient gating.
    blur_laplacian_variance: float = 45.0
    blur_edge_gradient_threshold: float = 22.0
    minimum_contrast_stddev: float = 12.0
    underexposed_mean: float = 30.0
    overexposed_mean: float = 240.0
    clipping_level: int = 250
    clipping_ratio: float = 0.08
    glare_ratio: float = 0.05
    shadow_ratio: float = 0.30
    shadow_level: int = 40
    min_short_edge_px: int = 160
    min_candidate_area_px: int = 5_000
    border_margin_px: int = 8


@dataclass
class QualityReport:
    image_quality: str  # GOOD, ACCEPTABLE, POOR, or INCONCLUSIVE
    quality_score: float | None  # Deprecated API field; never a confidence score.
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    retake_recommended: bool = False
    recommendation: str | None = None


class ImageQualityAssessor:
    def __init__(self, thresholds: QualityThresholds | None = None):
        self.thresholds = thresholds or QualityThresholds()

    def assess(
        self,
        image_bgr: np.ndarray,
        bbox: tuple[int, int, int, int] | None = None,
        candidate_mask: np.ndarray | None = None,
        screening_status: str = "UNCERTAIN",
        **legacy: Any,
    ) -> QualityReport:
        """Measure blur, illumination, clipping, glare, framing and resolution.

        ``legacy`` keeps callers using the former ``has_egg`` parameter from
        crashing, while deliberately not treating it as evidence of an egg.
        """
        del legacy
        if image_bgr is None or image_bgr.size == 0:
            return QualityReport(
                "POOR",
                None,
                [QualityWarning.INVALID_IMAGE],
                {},
                True,
                "The image could not be decoded. Select a valid JPEG, PNG, or WebP image.",
            )

        h, w = image_bgr.shape[:2]
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        metrics: dict[str, Any] = {"resolution": f"{w}x{h}", "capture_readiness_score": None}
        if candidate_mask is None or not np.any(candidate_mask):
            warning = (
                QualityWarning.UNSUPPORTED_BACKGROUND
                if screening_status == "UNSUPPORTED_BACKGROUND"
                else QualityWarning.NO_CANDIDATE
            )
            message = (
                "Use a contrasting matte background or controlled chamber so the subject boundary can be screened."
                if warning == QualityWarning.UNSUPPORTED_BACKGROUND
                else "No isolated candidate contour was available, so exposure was not assessed. Use one centered subject against a simpler background."
            )
            metrics.update({"exposure_region": "inconclusive_no_candidate_roi", "candidate_pixel_count": 0})
            return QualityReport("INCONCLUSIVE", None, [warning, QualityWarning.EXPOSURE_INCONCLUSIVE], metrics, True, message)

        pixels = gray[candidate_mask > 0]
        candidate_pixels = int(pixels.size)
        candidate_mean = float(np.mean(pixels))
        candidate_std = float(np.std(pixels))
        clipped_ratio = float(np.mean(pixels >= self.thresholds.clipping_level))
        dark_ratio = float(np.mean(pixels <= self.thresholds.shadow_level))

        # Compute ROI bounding coordinates
        x, y, bw, bh = bbox or cv2.boundingRect(cv2.findNonZero(candidate_mask))
        roi = gray[y:y + bh, x:x + bw]
        roi_mask = candidate_mask[y:y + bh, x:x + bw] > 0

        # Primary sharpness: Laplacian variance of candidate region
        laplacian_variance = float(cv2.Laplacian(roi, cv2.CV_32F).var())

        # Boundary edge sharpness (Tenengrad along candidate contour perimeter)
        kernel_edge = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        dilated = cv2.morphologyEx(candidate_mask, cv2.MORPH_DILATE, kernel_edge)
        eroded = cv2.morphologyEx(candidate_mask, cv2.MORPH_ERODE, kernel_edge)
        edge_band = (dilated > 0) & (eroded == 0)

        sobel_x_full = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
        sobel_y_full = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
        gradient_full = cv2.magnitude(sobel_x_full, sobel_y_full)

        edge_gradients = gradient_full[edge_band]
        edge_sharpness = float(np.percentile(edge_gradients, 85)) if edge_gradients.size > 0 else 0.0
        tenengrad = float(np.mean(edge_gradients ** 2)) if edge_gradients.size > 0 else 0.0

        # Glare detection within candidate ROI
        sobel_x_roi = cv2.Sobel(roi, cv2.CV_32F, 1, 0)
        sobel_y_roi = cv2.Sobel(roi, cv2.CV_32F, 0, 1)
        gradient_roi = cv2.magnitude(sobel_x_roi, sobel_y_roi)
        glare_ratio = float(np.mean((roi >= self.thresholds.clipping_level) & (gradient_roi > 50) & roi_mask))
        del sobel_x_full, sobel_y_full, sobel_x_roi, sobel_y_roi, gradient_roi

        metrics.update({
            "exposure_region": "candidate_roi",
            "candidate_pixel_count": candidate_pixels,
            "candidate_mean_intensity": round(candidate_mean, 2),
            "candidate_contrast_stddev": round(candidate_std, 2),
            "candidate_clipping_ratio": round(clipped_ratio, 4),
            "candidate_dark_ratio": round(dark_ratio, 4),
            "candidate_glare_ratio": round(glare_ratio, 4),
            "laplacian_variance": round(laplacian_variance, 2),
            "edge_sharpness": round(edge_sharpness, 2),
            "tenengrad": round(tenengrad, 2),
        })

        warnings: list[str] = []
        if min(w, h) < self.thresholds.min_short_edge_px or candidate_pixels < self.thresholds.min_candidate_area_px:
            warnings.append(QualityWarning.LOW_RESOLUTION)

        # Blur gating: Smooth eggs on plain backgrounds naturally have low interior texture.
        # An image is truly blurred if either:
        # 1. Both edge boundary sharpness AND Laplacian variance are below threshold, OR
        # 2. Laplacian variance is severely degraded (< 8.0, e.g. severe defocus / motion blur).
        is_blurred = (
            (edge_sharpness < self.thresholds.blur_edge_gradient_threshold and laplacian_variance < self.thresholds.blur_laplacian_variance)
            or (laplacian_variance < 8.0)
        )
        if is_blurred:
            warnings.append(QualityWarning.BLUR_DETECTED)

        if candidate_mean < self.thresholds.underexposed_mean:
            warnings.append(QualityWarning.UNDEREXPOSED)
        if candidate_mean > self.thresholds.overexposed_mean or clipped_ratio > self.thresholds.clipping_ratio:
            warnings.append(QualityWarning.OVEREXPOSED)
        if candidate_std < self.thresholds.minimum_contrast_stddev:
            warnings.append(QualityWarning.LOW_CONTRAST)
        if glare_ratio > self.thresholds.glare_ratio:
            warnings.append(QualityWarning.SPECULAR_REFLECTION)
        if dark_ratio > self.thresholds.shadow_ratio and candidate_mean >= self.thresholds.underexposed_mean:
            warnings.append(QualityWarning.STRONG_SHADOWS)
        if (
            x <= self.thresholds.border_margin_px
            or y <= self.thresholds.border_margin_px
            or x + bw >= w - self.thresholds.border_margin_px
            or y + bh >= h - self.thresholds.border_margin_px
        ):
            warnings.append(QualityWarning.BORDER_CLIPPED)

        blocking = {
            QualityWarning.LOW_RESOLUTION,
            QualityWarning.BLUR_DETECTED,
            QualityWarning.UNDEREXPOSED,
            QualityWarning.OVEREXPOSED,
            QualityWarning.BORDER_CLIPPED,
        }
        image_quality = "POOR" if blocking.intersection(warnings) else ("ACCEPTABLE" if warnings else "GOOD")
        return QualityReport(
            image_quality,
            None,
            warnings,
            metrics,
            bool(blocking.intersection(warnings)),
            self._recommendation(warnings),
        )

    @staticmethod
    def _recommendation(warnings: list[str]) -> str | None:
        guidance = {
            QualityWarning.BLUR_DETECTED: "Hold the camera steady and refocus before capture.",
            QualityWarning.UNDEREXPOSED: "Increase light on the candidate or use controlled candling illumination.",
            QualityWarning.OVEREXPOSED: "Reduce direct light or diffuse it to avoid clipping the candidate region.",
            QualityWarning.LOW_CONTRAST: "Increase separation between the candidate and its background.",
            QualityWarning.SPECULAR_REFLECTION: "Move or diffuse the light to reduce glare on the candidate.",
            QualityWarning.STRONG_SHADOWS: "Use more even illumination to reduce strong shadows across the candidate.",
            QualityWarning.BORDER_CLIPPED: "Keep the full candidate inside the frame with a visible margin.",
            QualityWarning.LOW_RESOLUTION: "Capture the image closer or with higher camera resolution.",
        }
        active = [guidance[w] for w in warnings if w in guidance]
        return " ".join(active) if active else None
