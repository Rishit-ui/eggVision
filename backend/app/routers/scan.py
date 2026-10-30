import json
import logging
import uuid
from pathlib import Path
from time import perf_counter

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.scan import (
    DirectScanCreate,
    ScanCreate,
    ScanResponse,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.services.cv_service import cv_service
from app.services.image_service import image_service
from app.services.scan_service import scan_service
from app.services.storage_service import storage_service

router = APIRouter(tags=["Scan"])
logger = logging.getLogger(__name__)


def scan_request_id(request: Request) -> str:
    """Use a safe client correlation id when supplied, otherwise generate one."""
    supplied = request.headers.get("X-Request-ID", "").strip()
    if supplied and len(supplied) <= 128 and "\n" not in supplied and "\r" not in supplied:
        return supplied
    return str(uuid.uuid4())


@router.post("/scan/upload-url", response_model=UploadUrlResponse)
async def get_upload_url(
    payload: UploadUrlRequest,
    request: Request,
    current_user: User | None = Depends(get_current_user),
):
    """
    Generate an S3 presigned PUT URL for direct client-to-storage upload,
    bypassing serverless request-body limits.
    """
    request_id = scan_request_id(request)
    if payload.file_size and payload.file_size > settings.UPLOAD_MAX_SIZE_MB * 1024 * 1024:
        logger.warning("upload_url_rejected request_id=%s category=file_too_large", request_id)
        raise HTTPException(status_code=413, detail="File too large")

    ext = Path(payload.filename).suffix.lower() or ".jpg"
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image format. Upload a JPEG, PNG, or WebP image.",
        )

    content_type = payload.content_type
    if content_type not in ["image/jpeg", "image/png", "image/webp"]:
        content_type = "image/jpeg"

    user_id = str(current_user.id) if current_user else "anonymous"
    object_key = f"uploads/{user_id}/{uuid.uuid4()}{ext}"

    try:
        upload_url = storage_service.generate_presigned_upload_url(
            key=object_key,
            content_type=content_type,
            expires_in=300,
        )
    except Exception as exc:
        logger.exception("presigned_url_generation_failed request_id=%s", request_id)
        raise HTTPException(
            status_code=502,
            detail="Storage service is temporarily unavailable for direct upload.",
        ) from exc

    return UploadUrlResponse(
        upload_url=upload_url,
        object_key=object_key,
        public_url=f"/api/v1/artifacts/{object_key}",
        expires_in=300,
    )


@router.post("/scan", response_model=ScanResponse, status_code=201)
async def create_scan(
    request: Request,
    response: Response,
    image: UploadFile | None = File(None),
    metadata: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    direct_scan: DirectScanCreate | None = Body(None),
    current_user: User | None = Depends(get_current_user),
):
    request_id = scan_request_id(request)
    response.headers["X-Request-ID"] = request_id
    started = perf_counter()
    # The router is protected in app.main, so reaching this point means auth
    # dependencies have completed successfully. Never log token material.
    logger.info("scan_stage=request_received request_id=%s", request_id)
    logger.info("scan_stage=authentication_completed request_id=%s", request_id)

    # 1. DIRECT STORAGE WORKFLOW (via object_key from presigned direct upload)
    if direct_scan and direct_scan.object_key:
        object_key = direct_scan.object_key.strip()
        user_id = str(current_user.id) if current_user else "anonymous"
        expected_prefix = f"uploads/{user_id}/"

        # Validate object ownership: key must belong to authenticated user
        if not object_key.startswith(expected_prefix) and getattr(current_user, "role", "") != "admin":
            logger.warning(
                "scan_rejected request_id=%s category=unauthorized_object_key key=%s",
                request_id,
                object_key,
            )
            raise HTTPException(status_code=403, detail="Access to this upload object is not authorized")

        try:
            file_data, content_type = await storage_service.get_image(object_key)
        except (FileNotFoundError, ClientError, ValueError):
            logger.exception("scan_failed request_id=%s category=direct_object_fetch", request_id)
            raise HTTPException(status_code=404, detail="Uploaded image was not found or expired")

        scan_create = direct_data_meta = direct_scan.metadata
        filename = Path(object_key).name
        original_image_url = f"/api/v1/artifacts/{object_key}"
        logger.info("scan_stage=image_received request_id=%s bytes=%s", request_id, len(file_data))

        is_valid, msg = image_service.validate_image(file_data)
        if not is_valid:
            logger.warning("scan_rejected request_id=%s category=image_validation", request_id)
            raise HTTPException(status_code=413 if msg == "File too large" else 400, detail=msg)
        logger.info(
            "scan_stage=image_validation_completed request_id=%s elapsed_ms=%.2f",
            request_id,
            (perf_counter() - started) * 1000,
        )
        logger.info(
            "scan_stage=original_image_storage_completed request_id=%s elapsed_ms=%.2f",
            request_id,
            (perf_counter() - started) * 1000,
        )

    # 2. MULTIPART FORM UPLOAD WORKFLOW
    else:
        if image is None or metadata is None:
            raise HTTPException(status_code=400, detail="Missing image or metadata")

        try:
            metadata_dict = json.loads(metadata)
            scan_create = ScanCreate(**metadata_dict)
        except Exception:
            logger.warning("scan_rejected request_id=%s category=invalid_metadata", request_id)
            raise HTTPException(status_code=400, detail="Invalid metadata format")

        file_data = await image.read()
        logger.info("scan_stage=image_received request_id=%s bytes=%s", request_id, len(file_data))

        is_valid, msg = image_service.validate_image(file_data)
        if not is_valid:
            logger.warning("scan_rejected request_id=%s category=image_validation", request_id)
            raise HTTPException(status_code=413 if msg == "File too large" else 400, detail=msg)
        logger.info("scan_stage=image_validation_completed request_id=%s elapsed_ms=%.2f", request_id, (perf_counter() - started) * 1000)

        try:
            content_type, extension = image_service.canonical_upload_details(file_data)
        except Exception:
            logger.exception("scan_failed request_id=%s category=image_canonicalization", request_id)
            raise HTTPException(status_code=400, detail="The uploaded image could not be processed.")
        filename = f"{uuid.uuid4()}{extension}"
        try:
            original_image_url = await storage_service.upload_image(file_data, filename, content_type)
        except (BotoCoreError, ClientError, OSError, TimeoutError):
            logger.exception("scan_failed request_id=%s category=original_image_storage", request_id)
            raise HTTPException(status_code=502, detail="Image storage is temporarily unavailable. Please try again.")
        except Exception:
            logger.exception("scan_failed request_id=%s category=original_image_storage", request_id)
            raise HTTPException(status_code=502, detail="Image storage failed. Please try again.")
        logger.info("scan_stage=original_image_storage_completed request_id=%s elapsed_ms=%.2f", request_id, (perf_counter() - started) * 1000)

    try:
        # CPU-intensive pipeline execution happens in a worker thread.
        cv_res = await cv_service.process_scan_image(file_data, filename, request_id)
    except (BotoCoreError, ClientError, OSError, TimeoutError):
        logger.exception("scan_failed request_id=%s category=normalized_image_storage", request_id)
        raise HTTPException(status_code=502, detail="Processed image storage is temporarily unavailable. Please try again.")
    except Exception:
        logger.exception("scan_failed request_id=%s category=cv_processing", request_id)
        raise HTTPException(status_code=502, detail="Image processing failed. Please try again.")
    finally:
        del file_data

    camera_metadata = scan_create.camera_metadata or {}
    camera_metadata["capture_context"] = {
        "egg_type": scan_create.egg_type,
        "storage_condition": scan_create.storage_condition,
        "temperature_c": scan_create.temperature,
        "humidity_percent": scan_create.humidity,
    }
    # Contour-derived metrics are research observations only. They are never
    # persisted as verified egg measurements without an egg-detection model.
    if cv_res.get("candidate_geometry"):
        camera_metadata["candidate_contour_geometry"] = cv_res["candidate_geometry"]
    if cv_res.get("metrics"):
        camera_metadata["cv_metrics"] = cv_res["metrics"]
    camera_metadata["analysis_evidence"] = cv_res.get("analysis", {
        "status": "INFERENCE_ERROR",
        "limitations": ["The capture analysis did not return evidence."],
    })

    logger.info("scan_stage=postgres_persistence_started request_id=%s", request_id)
    try:
        scan = await scan_service.create_scan(
            db=db,
            image_url=original_image_url,
            metadata=scan_create,
            processed_image_url=cv_res.get("processed_image_url"),
            image_quality=cv_res.get("image_quality"),
            image_quality_score=cv_res.get("quality_score"),
            image_quality_warnings=cv_res.get("warnings", []),
            camera_metadata=camera_metadata,
        )
    except SQLAlchemyError:
        logger.exception("scan_failed request_id=%s category=postgres_persistence", request_id)
        raise HTTPException(status_code=503, detail="Scan persistence is temporarily unavailable. Please try again.")
    logger.info("scan_stage=postgres_persistence_completed request_id=%s elapsed_ms=%.2f", request_id, (perf_counter() - started) * 1000)

    # Return complete response including dynamic gating fields
    try:
        response_data = ScanResponse.model_validate(scan).model_dump()
        response_data["retake_recommended"] = cv_res.get("retake_recommended", False)
        response_data["recommendation"] = cv_res.get("recommendation")
        response_data["analysis"] = cv_res.get("analysis")
        response_data["candidate_contour_geometry"] = cv_res.get("candidate_geometry")
        serialized = ScanResponse(**response_data)
    except Exception:
        logger.exception("scan_failed request_id=%s category=response_serialization", request_id)
        raise HTTPException(status_code=500, detail="Scan was saved but its response could not be prepared.")
    logger.info("scan_stage=response_serialization_completed request_id=%s elapsed_ms=%.2f", request_id, (perf_counter() - started) * 1000)
    return serialized
