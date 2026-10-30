# Capture screening

EggVision uses deterministic OpenCV capture screening, not a trained egg detector. It supports two acquisition contexts:

- `controlled_candling`: a dark-border frame where luminance separation is useful.
- `general_photograph`: a white, neutral, or dark-background photograph where LAB distance from the border background and edge closure are evaluated.

The screen returns a candidate contour only when a foreground proposal is isolated and meets documented area, aspect-ratio, and solidity gates. These are engineering constraints for image acquisition, not egg-likelihood parameters. A contour does not establish that an egg is present. The response distinguishes `NO_CANDIDATE_CONTOUR`, `UNSUPPORTED_BACKGROUND`, `MULTIPLE_CANDIDATES`, and `INVALID_IMAGE`.

## Capture metrics

When a candidate region is screened, blur, mean luminance, contrast, pixel clipping, glare, shadow coverage, framing, and resolution are measured inside that candidate ROI. Background brightness is deliberately excluded from exposure decisions; a white background alone cannot produce an overexposure finding. When no candidate ROI exists, exposure is reported as `EXPOSURE_ASSESSMENT_INCONCLUSIVE` rather than inferred from the whole frame.

Thresholds are declared in `ScreeningThresholds` and `QualityThresholds` in `ml/vision/`. They are configurable engineering defaults, covered by synthetic behavior tests, and must be calibrated against a particular camera and illumination rig before being used as a field acceptance procedure. EggVision does not present a capture score, AI confidence, freshness score, or safety conclusion.

## Guidance shown to users

- Bright uniform or white background: use a contrasting matte background or a controlled chamber.
- Dark image: add even illumination.
- Blur: refocus or stabilize the camera.
- Glare: diffuse or reposition the light.
- Strong shadows: use more even illumination.
- Frame clipping: keep the full candidate inside the frame.
- Multiple candidates: capture one subject at a time.

Even a clean capture remains only a research record until a separately trained and validated detector and prediction model are deployed.
