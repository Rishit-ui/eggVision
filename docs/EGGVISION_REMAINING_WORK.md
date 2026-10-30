# EggVision AI — Remaining Engineering Work & Technical Punchlist
**Document Version:** 1.0.0  
**Status:** Active Research Baseline  
**Classification:** Engineering Roadmap & Gap Analysis

---

## 1. Executive Status Overview

The software infrastructure, API execution paths, database transactions, computer vision screening, testing frameworks, and frontend web applications of EggVision AI are functional, tested, and verified. 

To transition from the current **Functional Research MVP** to a validated, production-grade egg quality decision system, the following empirical, physical, and scientific work remains to be executed.

---

## 2. Technical Punchlist by Engineering Discipline

### 2.1 Hardware & Physical Laboratory Chamber
- [ ] **Chamber Prototyping:** Laser-cut and assemble the $300 \times 200 \times 250\,mm$ matte acrylic enclosure specified in `docs/EGGVISION_OPTICAL_HARDWARE_DESIGN.md`.
- [ ] **Silicone Aperture Tooling:** Mold the Shore A 30 silicone sealing ring to ensure a tight optical seal around varied egg curvatures ($40–50\,mm$ diameter range).
- [ ] **Hardware Driver Daemon:** Write a lightweight Python capture daemon for the Raspberry Pi 4 to synchronize LED PWM intensity with camera autofocus capture upon button press.

### 2.2 Dataset Acquisition & Ground Truth Benchmarking
- [ ] **Procurement of Specimen Cohort:** Procure a minimum of 2,400 eggs across diverse shell varieties (white Leghorn, brown Rhode Island Red, tinted native breeds) from at least two distinct poultry farms.
- [ ] **Longitudinal Storage Trials:** Partition the specimen cohort into controlled storage chambers:
  - Chamber 1: Refrigerated ($4^\circ\text{C} \pm 0.5^\circ\text{C}$, $65\% \pm 5\%$ RH).
  - Chamber 2: Ambient Room ($22^\circ\text{C} \pm 1^\circ\text{C}$, $50\% \pm 5\%$ RH).
  - Chamber 3: Accelerated Warm ($32^\circ\text{C} \pm 1^\circ\text{C}$, $40\% \pm 5\%$ RH).
- [ ] **Destructive Laboratory Breakouts:** For every specimen, perform transillumination imaging, followed immediately by mass loss recording, float-glass breakout, tripod micrometer albumen height measurement, Haugh unit calculation, yolk index recording, and pH assay.
- [ ] **Dataset Publication:** Compile all images, masks, and breakout records into an immutable versioned dataset with `manifest.json`.

### 2.3 Machine Learning Model Development & Validation
- [ ] **Air-Cell Segmentation Network:** Train a lightweight U-Net (ResNet-18 or MobileNetV3 encoder) on annotated transillumination candling images to segment the air cell silhouette. Validate that Dice coefficient exceeds $0.92$ on independent test eggs.
- [ ] **Multimodal Freshness Regressor:** Train a gradient-boosted decision tree (XGBoost) or multi-layer perceptron combining the air cell area ratio with storage temperature, relative humidity, and storage duration to predict Haugh units.
- [ ] **Sign-off on Model Card:** Execute independent test evaluation ($n \ge 358$ eggs) verifying mean absolute error $MAE \le 4.0\,HU$. Register the validated checkpoint in the model registry and update `InferenceEngine`.

### 2.4 Cloud Infrastructure & Production Hardening
- [ ] **Production Object Storage Provisioning:** Set up an AWS S3, Cloudflare R2, or RustFS bucket; populate `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, and `S3_SECRET_KEY` in the Render dashboard; and switch `S3_REQUIRED=true`.
- [ ] **Secret Rotation Execution:** Run `openssl rand -hex 32` to rotate `JWT_SECRET` and `BOOTSTRAP_TOKEN` in Render settings.
- [ ] **Production Health Probe:** Set up a lightweight external HTTP ping to `https://eggvision-1.onrender.com/api/v1/health` once every 10 minutes to eliminate Render free-tier cold starts during laboratory working hours.
