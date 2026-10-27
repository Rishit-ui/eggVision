from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["Analytics"])

@router.get("/analytics")
async def get_analytics():
    raise HTTPException(status_code=501, detail="Not Implemented")
