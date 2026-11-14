from app.schemas.prediction import ModelInfoResponse
from app.services.model_loader import model_manager
from app.services.prediction_service import inference_engine
from fastapi import APIRouter

router = APIRouter(tags=["Model Info"])

@router.get("/model/info", response_model=ModelInfoResponse)
async def get_model_info():
    info = inference_engine.get_model_info()
    mgr_status = model_manager.get_status_summary()
    state = "MODEL_READY" if info.is_ready else mgr_status.get("state", "MODEL_NOT_READY")
    return ModelInfoResponse(
        model_version=info.version,
        model_type=info.model_type,
        is_ready=info.is_ready,
        description=info.description,
        dataset_version=info.dataset_version,
        metrics=info.metrics,
        trained_at=info.trained_at,
        state=state,
        artifact_available=True if info.is_ready else mgr_status.get("artifact_available", False),
        checksum_verified=True if info.is_ready else mgr_status.get("checksum_verified", False),
        runtime_available=True if info.is_ready else mgr_status.get("runtime_available", False),
        runtime_name=info.model_type if info.is_ready else mgr_status.get("runtime_name"),
    )
