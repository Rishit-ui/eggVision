# EggVision AI — Complete REST API Reference Manual
**API Version:** 1.0.0  
**Base URL (Local Development):** `http://localhost:8000/api/v1`  
**Base URL (Production Render):** `https://eggvision-1.onrender.com/api/v1`  
**OpenAPI Specification:** `https://eggvision-1.onrender.com/docs`

---

## 1. Global Request & Response Standards

### 1.1 Authentication
Endpoints marked **[Protected]** require an HTTP Bearer JWT token in the request header:
```http
Authorization: Bearer <jwt_access_token>
```
Tokens are issued via `POST /api/v1/auth/login` and expire after 60 minutes.

### 1.2 Request Correlation & Tracing
Clients may supply an optional `X-Request-ID` header ($1–128$ characters, printable ASCII without newlines) to correlate requests across client and server logs. If omitted or invalid, the API generates a standard UUIDv4. The active correlation ID is always returned in the response header:
```http
X-Request-ID: d5b4c1e2-789a-4bc0-a123-456789abcdef
```

### 1.3 Standard HTTP Status Codes
- `200 OK`: Request succeeded.
- `201 Created`: Resource successfully created.
- `400 Bad Request`: Malformed JSON, unparseable image bytes, or invalid metadata.
- `401 Unauthorized`: Missing or expired Bearer token.
- `403 Forbidden`: Insufficient role permissions.
- `404 Not Found`: Requested scan or resource does not exist.
- `413 Payload Too Large`: Image file exceeds the configured limit ($10\,\text{MB}$).
- `422 Unprocessable Entity`: Validation failure on request body fields.
- `502 Bad Gateway`: Downstream storage (S3) or CV processing failure.
- `503 Service Unavailable`: PostgreSQL persistence or Redis connectivity error.

---

## 2. Authentication Endpoints

### 2.1 User Login
`POST /api/v1/auth/login`
- **Access:** Public
- **Content-Type:** `application/json`
- **Request Body:**
```json
{
  "email": "researcher@eggvision.org",
  "password": "SecurePassword123!"
}
```
- **Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "e4b3c2d1-5678-4321-9abc-def012345678",
    "email": "researcher@eggvision.org",
    "role": "admin"
  }
}
```

### 2.2 User Logout
`POST /api/v1/auth/logout`
- **Access:** Public
- **Response (200 OK):** `{"message": "Logged out successfully"}`

### 2.3 Initial Administrator Bootstrap
`POST /api/v1/auth/bootstrap`
- **Access:** Public (Protected by server-side `BOOTSTRAP_TOKEN` environment secret)
- **Request Body:**
```json
{
  "email": "admin@eggvision.org",
  "password": "InitialAdminPassword123!",
  "bootstrap_token": "configured-secret-token-min-32-chars"
}
```
- **Response (201 Created):** Creates the initial administrator user if no administrator account exists.

---

## 3. Health & System Diagnostics

### 3.1 Deep Health Check
`GET /api/v1/health`
- **Access:** Public
- **Response (200 OK):**
```json
{
  "status": "ok",
  "environment": "production",
  "version": "1.0.0",
  "database": { "status": "ok", "latency_ms": 1.42 },
  "redis": { "status": "ok", "latency_ms": 0.85 },
  "storage": { "status": "ok", "type": "s3_compatible" },
  "model_service": {
    "status": "not_ready",
    "model_type": "placeholder",
    "message": "No trained model loaded."
  }
}
```

---

## 4. Scan & Capture Endpoints

### 4.1 Ingest New Scan
`POST /api/v1/scan` **[Protected]**
- **Content-Type:** `multipart/form-data`
- **Form Fields:**
  - `image`: Binary file (JPEG, PNG, or WebP; maximum 10 MB, maximum 25,000,000 pixels).
  - `metadata`: JSON string serialized from `ScanCreate` schema.

**Metadata JSON Schema:**
```json
{
  "egg_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "batch_id": "c1a2b3c4-d5e6-7890-1234-567890abcdef",
  "device_id": "d1a2b3c4-d5e6-7890-1234-567890abcdef",
  "egg_type": "white",
  "storage_condition": "refrigerated",
  "temperature": 4.5,
  "humidity": 65.0,
  "camera_metadata": { "iso": 100, "exposure_time": "1/60" }
}
```

**curl Example:**
```bash
curl -X POST "https://eggvision-1.onrender.com/api/v1/scan" \
  -H "Authorization: Bearer <jwt_access_token>" \
  -H "X-Request-ID: test-scan-001" \
  -F "image=@sample_egg.jpg;type=image/jpeg" \
  -F 'metadata={"egg_type":"white","temperature":4.5,"humidity":65.0}'
```

**Response (201 Created):**
```json
{
  "id": "7f8e9d0a-1b2c-3d4e-5f6a-7b8c9d0e1f2a",
  "egg_id": null,
  "batch_id": null,
  "original_image_url": "/api/v1/artifacts/7f8e9d0a-1b2c-3d4e-5f6a-7b8c9d0e1f2a.jpg",
  "processed_image_url": "/api/v1/artifacts/normalized_9a8b7c6d-5e4f-3a2b-1c0d-e9f8a7b6c5d4.jpg",
  "image_quality": "GOOD",
  "image_quality_score": null,
  "image_quality_warnings": [],
  "retake_recommended": false,
  "recommendation": null,
  "analysis": {
    "status": "UNCERTAIN",
    "capture_mode": "controlled_candling",
    "model": {
      "name": "contour_screening_v2",
      "version": "2",
      "task": "non_ml_candidate_contour_screen",
      "validated_egg_detector": false
    },
    "detections": [],
    "limitations": [
      "No trained, validated egg detector is installed.",
      "A contour compatible with the chamber silhouette is not proof that an egg is present."
    ],
    "message": "Candidate contour screened compatible with chamber aperture."
  },
  "candidate_contour_geometry": {
    "area": 128450,
    "width": 380,
    "height": 510,
    "aspect_ratio": 1.34,
    "centroid": [255, 255],
    "orientation_deg": 1.2
  },
  "capture_date": "2026-10-30T14:30:00Z",
  "created_at": "2026-10-30T14:30:01Z",
  "prediction": null
}
```

### 4.2 Retrieve Scan Details
`GET /api/v1/result/{id}` **[Protected]**
- **Parameters:** `id` (UUIDv4) in URL path.
- **Response (200 OK):** Returns complete `ScanResponse` matching the model above.

### 4.3 Scan History
`GET /api/v1/history?page=1&per_page=10` **[Protected]**
- **Query Parameters:** `page` (integer, default 1), `per_page` (integer, default 10, max 100).
- **Response (200 OK):**
```json
{
  "items": [ /* array of ScanResponse objects */ ],
  "total": 42,
  "page": 1,
  "per_page": 10,
  "pages": 5
}
```

---

## 5. Inference & Artifact Endpoints

### 5.1 Request Model Prediction
`POST /api/v1/predict` **[Protected]**
- **Request Body:** `{"scan_id": "7f8e9d0a-1b2c-3d4e-5f6a-7b8c9d0e1f2a"}`
- **Response (200 OK):**
```json
{
  "id": "1a2b3c4d-5e6f-7a8b-9c0d-e1f2a3b4c5d6",
  "scan_id": "7f8e9d0a-1b2c-3d4e-5f6a-7b8c9d0e1f2a",
  "freshness_class": null,
  "freshness_score": null,
  "estimated_age_min": null,
  "estimated_age_max": null,
  "predicted_haugh_unit": null,
  "confidence": null,
  "status": "model_not_ready",
  "explanation": ["No trained model is currently loaded. The system architecture is ready for model integration."],
  "created_at": "2026-10-30T14:30:05Z"
}
```

### 5.2 Stream Image Artifact
`GET /api/v1/artifacts/{filename}` **[Protected]**
- **Access:** Requires valid authentication token.
- **Behavior:** Streams the raw binary image from durable object storage (or local disk fallback) with proper MIME headers (`image/jpeg`, `image/png`). Protects research captures from unauthorized public internet harvesting.
