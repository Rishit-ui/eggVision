from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.scan import ScanResponse
from app.services.scan_service import scan_service

router = APIRouter(tags=["History"])

@router.get("/history", response_model=PaginatedResponse[ScanResponse])
async def get_history(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    items, total = await scan_service.list_scans(db, page, per_page)
    pages = (total + per_page - 1) // per_page
    
    return PaginatedResponse[ScanResponse](
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages
    )
