# API Reference

## Endpoints

### GET /api/v1/health
Check system status.
**Response**: `{"status": "ok"}`

### POST /api/v1/scan
Upload an image of an egg for processing.
**Request**: `multipart/form-data` with `file`
**Response**: `201 Created` with image ID

### POST /api/v1/predict
Run model inference on a previously uploaded image.
**Request**: JSON `{"image_id": "123", "metadata": {...}}`
**Response**: JSON with prediction results or `model_not_ready` status.

## Future Plans
- Authentication (JWT)
- Rate limiting
