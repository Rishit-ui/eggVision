from app.schemas.prediction import ModelInfoResponse
from app.services.model_loader import model_manager
from fastapi import APIRouter

router = APIRouter(tags=["Model Info"])

@router.get("/model/info", response_model=ModelInfoResponse)
async def get_model_info():
    info = model_manager.get_engine().get_model_info()
    mgr_status = model_manager.get_status_summary()
    is_ready = bool(mgr_status.get("is_ready", False))
    return ModelInfoResponse(
        model_version=info.version,
        model_type=info.model_type,
        is_ready=is_ready,
        description=info.description,
        dataset_version=info.dataset_version,
        metrics=info.metrics,
        trained_at=info.trained_at,
        state=mgr_status.get("state", "MODEL_NOT_READY"),
        artifact_available=bool(mgr_status.get("artifact_available", False)),
        checksum_verified=bool(mgr_status.get("checksum_verified", False)),
        runtime_available=bool(mgr_status.get("runtime_available", False)),
        runtime_name=mgr_status.get("runtime_name"),
    )
