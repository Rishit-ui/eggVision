# API Reference

## Endpoints

### GET /api/v1/health
Check system status.
**Response**: component health statuses for database, Redis, storage, and model service.

### POST /api/v1/scan
Upload an image of an egg for processing.
**Request**: `multipart/form-data` with `image` and JSON `metadata`.
**Response**: `201 Created` with scan ID, image-quality outcome, warnings, and processed artifact URL.

### POST /api/v1/predict
Run model inference on a previously uploaded image.
**Request**: JSON `{"scan_id": "uuid"}`
**Response**: JSON with prediction results or `model_not_ready` status.

### POST /api/v1/eggs
Register an egg with a traceable ID before capture. This is the first step in the laboratory data-collection workflow.

### POST /api/v1/ground-truth
Record measured Haugh Unit, albumen pH, weight, and observations after the intact image is captured and the egg is opened for lab measurement.

### POST /api/v1/batch
Register a batch. Use the returned UUID as `batch_id` when uploading scans.

### GET /api/v1/dashboard
Returns observed scan quality and prediction-service statuses. It does not fabricate freshness distributions.

Use `/docs` on the running backend for the authoritative OpenAPI request and response schemas.
