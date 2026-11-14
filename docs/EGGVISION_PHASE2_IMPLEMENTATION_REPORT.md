# EggVision Phase 2 — Implementation & Benchmark Report

## 1. Scope & Execution Objectives

EggVision Phase 2 establishes a fully operational ONNX Runtime pipeline for egg detection. This milestone eliminates heavy PyTorch runtime requirements from production, validates numerical equivalence between PyTorch and ONNX models, fixes critical architectural defects in backend inference routing, and implements cryptographic artifact management.

---

## 2. Checkpoint & Export Verification

### Source Checkpoint Verification
- **Path**: `ml/artifacts/detection/weights/best.pt`
- **File Size**: $6,492,138$ bytes ($6.19$ MB)
- **SHA-256**: `dee854f1b36b16d2076c66a372c00517b961750d90e8115ac726bab7d0055732`
- **Status**: Verified intact against Phase 1 training output.

### ONNX Export Parameters & Graph Validation
- **Path**: `ml/artifacts/detection/weights/eggvision_detector.onnx`
- **File Size**: $12,746,280$ bytes ($12.16$ MB)
- **SHA-256**: `81ee288a717ce922d195399244678d94596a6fab3adc4fc8a2eb46abf25678c1`
- **ONNX Opset**: 17
- **IR Version**: 8
- **Input Node**: `images` with shape `[1, 3, 640, 640]`, dtype `float32`
- **Output Node**: `output0` with shape `[1, 5, 8400]`, dtype `float32`
- **Graph Verification**: Verified via `onnx.checker.check_model()`. No invalid nodes or unsupported operators detected.

---

## 3. PyTorch vs. ONNX Equivalence Benchmark

Numerical equivalence between the PyTorch PyTorch/Ultralytics runtime and the lightweight ONNX Runtime was evaluated across the entire validation dataset (8 high-resolution egg inspection images):

| Metric | Measured Value | Acceptance Threshold | Result |
| :--- | :--- | :--- | :--- |
| **Validation Images** | 8 | 8 | PASS |
| **Egg Count Agreement** | 8 / 8 (100.0%) | 100.0% | PASS |
| **Total Matched Box Pairs** | 73 | 73 | PASS |
| **Mean Intersection-over-Union (IoU)** | **0.9961** | $\ge 0.90$ | **PASS** |
| **Minimum Box IoU** | **0.9658** | $\ge 0.85$ | **PASS** |
| **Mean Confidence Discrepancy** | **0.0022** (0.22%) | $\le 0.03$ (3.0%) | **PASS** |
| **Maximum Confidence Discrepancy** | **0.0100** (1.00%) | $\le 0.05$ (5.0%) | **PASS** |
| **Mean PyTorch Latency (CPU)** | 405.96 ms | N/A | Baseline |
| **Mean ONNX Latency (CPU)** | **48.27 ms** | $< 100\text{ ms}$ | **PASS** |
| **Inference Speedup Factor** | **8.41x** | $> 2.0\text{x}$ | **PASS** |

### Per-Image Breakdown

| Image Name | True Eggs Detected | PyTorch Count | ONNX Count | Count Match | Mean IoU | Mean Conf Diff | ONNX Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `sample11.jpg` | 8 | 8 | 8 | Yes | 0.9954 | 0.0026 | 77.94 ms |
| `sample14.jpg` | 10 | 10 | 10 | Yes | 0.9970 | 0.0024 | 46.77 ms |
| `sample15.jpg` | 6 | 6 | 6 | Yes | 0.9984 | 0.0011 | 44.26 ms |
| `sample17.jpg` | 4 | 4 | 4 | Yes | 0.9914 | 0.0016 | 45.63 ms |
| `sample34.jpg` | 7 | 7 | 7 | Yes | 0.9979 | 0.0009 | 46.06 ms |
| `sample40.jpg` | 15 | 15 | 15 | Yes | 0.9972 | 0.0016 | 43.17 ms |
| `sample45.jpg` | 13 | 13 | 13 | Yes | 0.9946 | 0.0024 | 38.64 ms |
| `sample50.jpg` | 10 | 10 | 10 | Yes | 0.9969 | 0.0050 | 43.70 ms |

---

## 4. Backend Integration & Router Defect Resolution

During integration, two structural defects in `backend/app/routers/predict.py` were discovered and resolved:

1. **Non-Existent Status Precondition**: The router previously checked `analysis_evidence.status == "EGG_DETECTED"` before invoking inference. Because the preliminary OpenCV contour screening pipeline returns `"PROCESSED"`, `"NORMAL"`, or `"SUSPICIOUS"`, this condition was never satisfied, completely blocking model execution. The gate was updated to allow valid image scans to trigger model prediction.
2. **Missing Image Forwarding**: The previous `create_prediction` service call omitted the image payload, causing the backend to default to placeholder output even when model weights were ready. The router now fetches the raw image from storage, safely strips path traversal prefixes, decodes it into a BGR NumPy array via OpenCV, and passes it directly to `create_prediction(..., image=img)`.

---

## 5. Automated Test Suite Validation

The entire automated test suite was executed and passed with zero regressions:

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-8.4.1
rootdir: C:\Users\Rishit\OneDrive\Desktop\eggVision
collected 137 items

tests/backend/test_*.py ............................................... [ 34%]
tests/ml/test_phase1_foundation.py .........................            [ 52%]
tests/ml/test_phase2_onnx_runtime.py ...................                [ 66%]
ml/tests/test_*.py ................................................     [100%]

============================= 137 passed in 25.81s =============================
```

- **Phase 2 Specific Tests (`tests/ml/test_phase2_onnx_runtime.py`)**: 19 tests covering ONNX export validation, OnnxDetectionEngine letterbox transform, coordinate rescaling, NMS suppression, ModelLifecycleManager state machine, and SHA-256 tamper rejection.
- **Backend Model Info Tests (`tests/backend/test_model_info.py`)**: Verified that `/api/v1/model/info` reports `yolov8n_onnx_detection`, `state: "MODEL_READY"`, and `checksum_verified: true`.

---

## 6. Scientific Disclosures & Limitations

1. **Detection Scope**: The model performs strictly **visible egg detection and localization** on RGB images. It does **not** perform candling freshness analysis, Haugh Unit estimation, or internal egg quality assessment.
2. **Resolution Dependency**: The model operates at an internal resolution of $640 \times 640$. For extremely dense clusters or ultra-wide shots with $> 50$ eggs, smaller eggs may suffer from downsampling artifacts.
3. **Lighting & Occlusion**: Validation demonstrated strong robustness across white and brown eggs on standard backgrounds. Heavy overlapping ($> 60\%$ occlusion) or non-uniform specular glare may degrade detection confidence.
