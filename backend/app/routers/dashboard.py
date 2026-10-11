from fastapi import APIRouter

router = APIRouter(tags=["Dashboard"])

@router.get("/dashboard")
async def get_dashboard():
    return {
        "total_scans": 0,
        "fresh_eggs": 0,
        "spoiled_eggs": 0,
        "recent_activity": []
    }
