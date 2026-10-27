"""Data-collection endpoints for the laboratory validation workflow."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.egg import Egg
from app.models.ground_truth import GroundTruth
from app.schemas.research import EggCreate, EggResponse, GroundTruthCreate, GroundTruthResponse

router = APIRouter(tags=["Research data"])


@router.post("/eggs", response_model=EggResponse, status_code=status.HTTP_201_CREATED)
async def register_egg(payload: EggCreate, db: AsyncSession = Depends(get_db)):
    """Create a traceable egg record before non-destructive capture and lab measurement."""
    egg = Egg(**payload.model_dump())
    db.add(egg)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise HTTPException(status_code=409, detail="An egg with this egg_id already exists") from error
    await db.refresh(egg)
    return egg


@router.post("/ground-truth", response_model=GroundTruthResponse, status_code=status.HTTP_201_CREATED)
async def record_ground_truth(payload: GroundTruthCreate, db: AsyncSession = Depends(get_db)):
    """Record laboratory observations after an intact egg has been captured."""
    egg = (await db.execute(select(Egg.id).where(Egg.id == payload.egg_id))).scalar_one_or_none()
    if egg is None:
        raise HTTPException(status_code=404, detail="Egg not found. Register the egg before adding ground truth.")
    if all(value is None for value in (payload.haugh_unit, payload.albumen_ph, payload.weight, payload.observations)):
        raise HTTPException(status_code=422, detail="Provide at least one measured value or observation.")
    ground_truth = GroundTruth(**payload.model_dump(exclude_none=True))
    db.add(ground_truth)
    await db.commit()
    await db.refresh(ground_truth)
    return ground_truth


@router.get("/eggs/{egg_id}/ground-truth", response_model=list[GroundTruthResponse])
async def get_ground_truth(egg_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(GroundTruth).where(GroundTruth.egg_id == egg_id).order_by(GroundTruth.measured_at.desc())
    )
    return list(result.scalars().all())
