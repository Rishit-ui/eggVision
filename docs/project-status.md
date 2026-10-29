# Project status

## Current release: research data-collection MVP

The application can launch as a controlled candling capture and research-data platform. It stores scans, rejects poor images, records candidate contours and capture metadata, registers batches, supports lab ground-truth entry through the API, and exposes real operational counts. A candidate contour is not treated as proof of egg presence.

## Completed software capabilities

- Next.js web application with landing, scan, result, history, dashboard, batch, about, and sign-in pages.
- FastAPI API with OpenAPI documentation, image upload validation, image-quality gating, scan records, batch registration, health reporting, and model status reporting.
- OpenCV baseline pipeline for image decoding, controlled-chamber candidate-contour screening, contour segmentation, normalization, blur/exposure/contrast/glare checks, and retake guidance. It is not a trained egg detector.
- PostgreSQL schema and Alembic migration for scans, eggs, batches, devices, sensor readings, ground truth, models, users, and audit-log storage.
- Laboratory data APIs for traceable egg registration and Haugh Unit, pH, weight, and observations after capture.
- Docker Compose local stack, migration entrypoint, environment template, CI workflow, and Windows run instructions.
- Production security controls: strong-secret checks, restricted CORS configuration, production authentication gate, one-time administrator bootstrap, JWT login, and protected API routes.

## Deliberately unavailable until validation

- Fresh, Okay, Old classification and freshness score.
- Quality-equivalent age or Haugh Unit prediction.
- Air-cell segmentation/measurement, yolk analysis, crack localization, blood-spot detection, and Grad-CAM.
- Accuracy, F1, MAE, latency, or any other model-performance claim.

The app returns `MODEL_NOT_READY` instead of fabricating these outputs.

## Work that requires real project inputs

These items cannot be completed by software alone:

1. Build the dark candling chamber and stabilize the camera, LED, diffuser, exposure, and egg holder.
2. Collect intact egg images across farms, shell types, storage temperatures, cameras, and ages.
3. Measure ground truth with a documented laboratory protocol after capture.
4. Train candidate models with egg-level and farm-level separation.
5. Evaluate calibration, subgroup performance, and abstention behavior on held-out data.
6. Approve acceptance criteria with the project’s poultry/food-science leads before enabling model output.

The validation evidence required for steps 2–6 is defined in `docs/research.md`.

## Completion estimate

Against the original end-state prompt, about 35% of the software architecture is implemented and roughly 0% of the scientific model-validation work is complete because no dataset, ground truth, trained model, or validation report is present. The platform is launchable now as a research data-collection MVP. It is not launchable as a trusted freshness decision system until the validation work above is complete.
