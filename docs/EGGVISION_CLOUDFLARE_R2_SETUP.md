# Cloudflare R2 Model Storage Setup & Operational Runbook

This runbook details the setup, least-privilege scoping, and deployment instructions for hosting EggVision AI model artifacts on **Cloudflare R2**.

---

## 1. Cloudflare R2 Architecture Overview

Cloudflare R2 provides S3-compatible object storage with **zero egress fees**, making it optimal for high-frequency model weight downloads across container restarts and autoscaling events.

```mermaid
flowchart LR
    Dev[MLOps Pipeline / Publisher] -->|Upload Model & Manifest| R2[Cloudflare R2: eggvision-models]
    R2 -->|Secure Egress (Zero Fee)| Render[Render Backend: eggVision-1]
```

### Storage Characteristics:
- **Bucket Name:** `eggvision-models`
- **Region:** `auto` (Cloudflare automatically routes to closest low-latency storage)
- **Signature Version:** `s3v4`
- **Endpoint Pattern:** `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`

---

## 2. Bucket Creation via Cloudflare Dashboard / CLI

### Step 1: Create Bucket
1. Log in to the [Cloudflare Dashboard](https://dash.cloudflare.com/).
2. Navigate to **R2 Object Storage** > **Overview**.
3. Click **Create Bucket**.
4. Name the bucket `eggvision-models`.
5. Select **Automatic** location hint.
6. Click **Create Bucket**.

### Step 2: Generate Least-Privilege API Tokens

Do not use global account API keys. Create two scoped tokens:

#### A. Production Read-Only Token (for Render Backend)
- **Token Name:** `eggvision-backend-models-readonly`
- **Permissions:** `Object Read Only`
- **Bucket Scope:** Apply to specific bucket: `eggvision-models`
- **TTL:** 1 year (or indefinite according to organizational policy)

Record the generated:
- `Access Key ID` (e.g. `d7a8b9...`)
- `Secret Access Key` (e.g. `f1e2d3...`)
- `Endpoint URL` (`https://<ACCOUNT_ID>.r2.cloudflarestorage.com`)

#### B. MLOps Publisher Token (for CI / ML Release Engineer)
- **Token Name:** `eggvision-mlops-models-readwrite`
- **Permissions:** `Object Read & Write`
- **Bucket Scope:** Apply to specific bucket: `eggvision-models`

---

## 3. PowerShell Local & Verification Commands

### Step 1: Configure Environment Variables in PowerShell

```powershell
$env:MODEL_S3_ENDPOINT = "https://<ACCOUNT_ID>.r2.cloudflarestorage.com"
$env:MODEL_S3_BUCKET = "eggvision-models"
$env:MODEL_S3_ACCESS_KEY = "<YOUR_MLOPS_ACCESS_KEY_ID>"
$env:MODEL_S3_SECRET_KEY = "<YOUR_MLOPS_SECRET_ACCESS_KEY>"
$env:MODEL_S3_REGION = "auto"
```

### Step 2: Publish Artifact to R2

```powershell
python ml/scripts/publish_model_artifact.py `
  --onnx-path ml/artifacts/detection/weights/eggvision_detector.onnx `
  --pt-path ml/artifacts/detection/weights/best.pt `
  --metadata ml/artifacts/detection/model_metadata.json `
  --onnx-meta ml/artifacts/detection/onnx_metadata.json `
  --equiv-report ml/artifacts/detection/onnx_equivalence_report.json `
  --manifest-output ml/artifacts/detection/manifest.json `
  --report-output ml/artifacts/detection/publish_report.json `
  --prefix eggvision/detection/v1
```

**Expected Output:**
```text
=== PUBLISH ARTIFACT SUMMARY ===
Status:       SUCCESS_VERIFIED
Artifact Key: eggvision/detection/v1/81ee288a717ce922d195399244678d94596a6fab3adc4fc8a2eb46abf25678c1/model.onnx
ONNX SHA-256: 81ee288a717ce922d195399244678d94596a6fab3adc4fc8a2eb46abf25678c1
Manifest:     ml/artifacts/detection/manifest.json
```

### Step 3: Verify Remote Object in R2

```powershell
python ml/scripts/verify_model_artifact.py `
  --s3-key "eggvision/detection/v1/81ee288a717ce922d195399244678d94596a6fab3adc4fc8a2eb46abf25678c1/model.onnx" `
  --expected-sha "81ee288a717ce922d195399244678d94596a6fab3adc4fc8a2eb46abf25678c1"
```

**Expected Output:**
```text
=== ARTIFACT VERIFICATION SUCCESSFUL ===
Status:   VERIFIED
SHA-256:  81ee288a717ce922d195399244678d94596a6fab3adc4fc8a2eb46abf25678c1
Size:     12,746,280 bytes
Runtime:  Ready (output shape: [1, 5, 8400])
```

### Step 4: Verify Local Artifact

```powershell
python ml/scripts/verify_model_artifact.py `
  --onnx-path ml/artifacts/detection/weights/eggvision_detector.onnx `
  --manifest ml/artifacts/detection/manifest.json
```

**Expected Output:**
```text
=== ARTIFACT VERIFICATION SUCCESSFUL ===
Status:   VERIFIED
SHA-256:  81ee288a717ce922d195399244678d94596a6fab3adc4fc8a2eb46abf25678c1
Size:     12,746,280 bytes
Runtime:  Ready (output shape: [1, 5, 8400])
```

---

## 4. Render Production Environment Configuration

In the Render dashboard for service `eggVision-1`, navigate to **Environment** and set:

```bash
# Model Runtime Identity
MODEL_VERSION="v1"
MODEL_ARTIFACT_KEY="eggvision/detection/v1/81ee288a717ce922d195399244678d94596a6fab3adc4fc8a2eb46abf25678c1/model.onnx"
MODEL_ARTIFACT_SHA256="81ee288a717ce922d195399244678d94596a6fab3adc4fc8a2eb46abf25678c1"

# Cloudflare R2 Model Credentials (Read-Only)
MODEL_S3_ENDPOINT="https://<ACCOUNT_ID>.r2.cloudflarestorage.com"
MODEL_S3_BUCKET="eggvision-models"
MODEL_S3_ACCESS_KEY="<YOUR_READONLY_ACCESS_KEY_ID>"
MODEL_S3_SECRET_KEY="<YOUR_READONLY_SECRET_ACCESS_KEY>"
MODEL_S3_REGION="auto"
```

> [!IMPORTANT]
> Do NOT set `S3_ENDPOINT`, `S3_ACCESS_KEY`, etc. for models. `S3_*` is reserved strictly for user scan image uploads.
