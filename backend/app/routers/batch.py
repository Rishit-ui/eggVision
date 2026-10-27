import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.batch import Batch
from app.schemas.batch import BatchCreate, BatchResponse

router = APIRouter(tags=["Batch"])

@router.post("/batch", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
async def create_batch(payload: BatchCreate, db: AsyncSession = Depends(get_db)):
    """Register a batch before associating captures with it."""
    batch = Batch(**payload.model_dump())
    db.add(batch)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A batch with this batch_id already exists") from error
    await db.refresh(batch)
    return batch

@router.get("/batch/{batch_id}")
async def get_batch(batch_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    batch = (await db.execute(select(Batch).where(Batch.id == batch_id))).scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch
