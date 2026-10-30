# EggVision AI — Formal Machine Learning Model Card
**Document Version:** 1.0.0  
**Format:** Mitchell et al. (2019) Model Cards for Model Reporting  
**Model Name:** `EggVision-Screening-Placeholder`  
**Current Registered Version:** `0.1.0`  
**Deployment Status:** `MODEL_NOT_READY` (Placeholder Engine Active)

---

## 1. Model Details

- **Developing Organization:** EggVision AI Research Project.
- **Model Type:** Heuristic Optical Candidate Screener & Morphometric Normalizer (`ml.vision.VisionPipeline`) paired with an abstract inference placeholder (`ml.inference.PlaceholderEngine`).
- **Checkpoints / Weights:** No machine learning checkpoint weights are currently loaded.
- **License:** MIT License.
- **Contact:** Research IT Supervisor (`admin@eggvision.org`).

---

## 2. Intended Use & Scope

### 2.1 Primary Intended Uses
- Real-time screening of poultry egg capture frames inside controlled scanning chambers.
- Identification of capture flaws (blur, specular glare, deep shadows, frame boundary clipping, low resolution).
- Geometric normalization ($512 \times 512$ canonical orientation) to support future model training.
- Longitudinal recording of environmental telemetry (storage duration, temperature, humidity) linked to physical specimens.

### 2.2 Explicit Out-of-Scope & Prohibited Uses
- **Food Safety Decisions:** The system **must not** be used to certify eggs as safe for human consumption or free from pathogens (*Salmonella enteritidis*, *Escherichia coli*).
- **Commercial USDA Grading:** The current software cannot substitute for an authorized USDA or EU egg candling inspector.
- **Automated Processing Lines:** The system is not rated for high-speed conveyor sorting ($> 60\,\text{eggs/minute}$).

---

## 3. Factors, Subpopulations & Environmental Sensitivity

The optical performance of capture screening is sensitive to:
1. **Eggshell Pigmentation:** Heavy brown and dark speckled eggshells exhibit significantly higher light attenuation ($> 10\times$ extinction coefficient compared to white shells), requiring higher LED transillumination intensity to illuminate internal air cells.
2. **Ambient Stray Light:** Operating outside a sealed enclosure allows extraneous reflections that corrupt Laplacian blur and shadow calculations.
3. **Dust & Shell Contamination:** Surface feather debris or manure can distort contour solidity calculations and mimic shell cracks.

---

## 4. Current Quantitative Performance & Evaluation

- **Egg Detection Accuracy:** $0\%$ ML-driven detection (operates via non-ML candidate contour screening).
- **Model Readiness:** `is_ready() == False`.
- **Inference Time:** $0.0\,\text{ms}$ (Placeholder returns immediately).
- **Haugh Unit Prediction Error:** Not applicable (no predictions generated).

---

## 5. Ethical Considerations & Consumer Safety Disclaimers

1. **Anti-Hallucination Policy:** Under no circumstances will EggVision synthesize or fake an AI prediction, confidence percentage, or freshness grade.
2. **Foodborne Illness Mitigation:** Consuming spoiled or contaminated eggs poses severe health risks (salmonellosis). Because optical candling cannot detect microbial contamination, EggVision explicitly informs users that optical captures cannot guarantee biological safety.
3. **Data Integrity:** Scans recorded under this system maintain provenance linking the raw image, camera parameters, and physical specimen UUID for auditable scientific review.
