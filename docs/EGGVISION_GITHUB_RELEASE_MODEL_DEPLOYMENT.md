# EggVision Model Deployment with GitHub Release Assets

This is the no-object-storage deployment path for the ONNX detector. The model binary is hosted as a public GitHub Release asset; the backend downloads it over HTTPS and verifies its SHA-256 digest before ONNX Runtime can load it.

## 1. Publish the model asset

1. Confirm the model is the validated ONNX export, not the PyTorch `.pt` checkpoint.
2. Confirm its digest locally:
   ```powershell
   Get-FileHash .\ml\artifacts\detection\weights\eggvision_detector.onnx -Algorithm SHA256
   ```
3. In GitHub, open **Rishit-ui/eggVision → Releases → Draft a new release**.
4. Use tag `model-v1.0.0` and title `EggVision ONNX Detector v1.0.0`.
5. Attach `eggvision_detector.onnx` as a release asset. Do not commit model weights into the Git repository.
6. Publish the release and copy the asset's browser download URL. It must be an HTTPS URL.

The current validated model SHA-256 is:

```text
81ee288a717ce922d195399244678d94596a6fab3adc4fc8a2eb46abf25678c1
```

Always recompute the hash of the exact file you upload. Do not rely on this documented value if the model file changes.

## 2. Configure Render after the release is published

On Render, open the existing `eggVision-1` backend service → Environment. Add:

- `MODEL_ARTIFACT_URL`: the exact HTTPS browser download URL of the GitHub Release asset
- `MODEL_ARTIFACT_SHA256`: the verified 64-character SHA-256 digest of that exact asset
- `MODEL_ARTIFACT_MAX_BYTES`: `100000000` (optional; default is 100 MB)
- `MODEL_VERSION`: `1.0.0`

For this path, leave the following model-storage variables unset:

- `MODEL_S3_ENDPOINT`
- `MODEL_S3_ACCESS_KEY`
- `MODEL_S3_SECRET_KEY`
- `MODEL_ARTIFACT_KEY`

Do not modify the existing image-storage `S3_*` settings. Do not modify PostgreSQL, Redis, authentication, or frontend environment variables for this model change.

Save the environment changes and deploy the intended backend commit only after the code change has passed CI and been merged.

## 3. Verify production readiness

After deployment, check:

```powershell
Invoke-RestMethod https://eggvision-1.onrender.com/api/v1/model/info | ConvertTo-Json -Depth 8
Invoke-RestMethod https://eggvision-1.onrender.com/api/v1/health | ConvertTo-Json -Depth 8
```

Expected model lifecycle fields:

- `state`: `MODEL_READY`
- `artifact_available`: `true`
- `checksum_verified`: `true`
- `runtime_available`: `true`
- `runtime_name`: `onnxruntime`
- `is_ready`: `true`

If the download fails, the service must remain on its safe placeholder path. A checksum mismatch must produce `MODEL_INTEGRITY_FAILED`; never remove checksum verification to make deployment pass.

## 4. Security and limitations

- GitHub Release assets in this public repository are publicly downloadable. Do not upload secrets, private data, or user images as release assets.
- The configured URL must use HTTPS. Redirects to non-HTTPS URLs are rejected.
- Downloads are streamed, bounded by `MODEL_ARTIFACT_MAX_BYTES`, written to a temporary file, SHA-256 verified, and atomically moved into a content-addressed cache.
- The SHA-256 value is the integrity trust anchor. HTTPS alone does not prove that the file is the intended model.
- GitHub is a convenient public artifact host, not a private model registry. If the repository becomes private or release downloads become unavailable, use an authenticated artifact provider.
- This detector identifies visible egg objects only. It does not assess internal freshness, Haugh Units, pathogens, or food safety.
