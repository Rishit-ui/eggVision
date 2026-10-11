import uuid
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["Batch"])

@router.post("/batch")
async def create_batch():
    raise HTTPException(status_code=501, detail="Not Implemented")

@router.get("/batch/{batch_id}")
async def get_batch(batch_id: uuid.UUID):
    raise HTTPException(status_code=501, detail="Not Implemented")
