from fastapi import APIRouter
from app.schemas.prediction import ModelInfoResponse
from app.services.prediction_service import inference_engine

router = APIRouter(tags=["Model Info"])

@router.get("/model/info", response_model=ModelInfoResponse)
async def get_model_info():
    info = inference_engine.get_model_info()
    return ModelInfoResponse(
        model_version=info.version,
        model_type=info.model_type,
        is_ready=info.is_ready,
        description=info.description,
        dataset_version=info.dataset_version,
        metrics=info.metrics,
        trained_at=info.trained_at,
    )
