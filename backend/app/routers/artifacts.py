"""Serve stored artifacts without exposing storage credentials or filesystem paths."""

from app.services.storage_service import storage_service
from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

router = APIRouter(tags=["Artifacts"])


@router.get("/artifacts/{filename:path}", include_in_schema=False)
async def get_artifact(filename: str):
    try:
        content, content_type = await storage_service.get_image(filename)
    except (FileNotFoundError, ClientError, ValueError):
        raise HTTPException(status_code=404, detail="Artifact not found")
    return Response(content=content, media_type=content_type, headers={"Cache-Control": "private, max-age=3600"})
