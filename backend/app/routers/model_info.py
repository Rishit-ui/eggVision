from fastapi import APIRouter
from app.schemas.prediction import ModelInfoResponse

router = APIRouter(tags=["Model Info"])

@router.get("/model/info", response_model=ModelInfoResponse)
async def get_model_info():
    return ModelInfoResponse(
        model_version="0.0.0",
        is_ready=False,
        description="no model loaded"
    )
