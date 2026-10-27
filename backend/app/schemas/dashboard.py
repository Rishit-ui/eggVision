from pydantic import BaseModel

from .common import CountByLabel


class DashboardResponse(BaseModel):
    total_scans: int
    usable_scans: int
    retake_scans: int
    model_ready: bool
    image_quality_distribution: list[CountByLabel]
    prediction_status_distribution: list[CountByLabel]
    freshness_distribution: list[CountByLabel]
