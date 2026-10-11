import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from app.models.batch import Batch
from app.models.scan import Scan
from app.models.prediction import Prediction
from app.models.sensor_reading import SensorReading
from app.schemas.scan import ScanCreate

class ScanService:
    async def create_scan(
        self,
        db: AsyncSession,
        image_url: str,
        metadata: ScanCreate,
        processed_image_url: str | None = None,
        image_quality: str | None = None,
        image_quality_score: float | None = None,
        image_quality_warnings: list | None = None,
        camera_metadata: dict | None = None,
    ) -> Scan:
        scan = Scan(
            original_image_url=image_url,
            processed_image_url=processed_image_url,
            image_quality=image_quality,
            image_quality_score=image_quality_score,
            image_quality_warnings=image_quality_warnings or [],
            egg_id=metadata.egg_id,
            batch_id=metadata.batch_id,
            device_id=metadata.device_id,
            camera_metadata=camera_metadata or metadata.camera_metadata
        )
        db.add(scan)
        await db.commit()
        if metadata.batch_id:
            await db.execute(
                update(Batch)
                .where(Batch.id == metadata.batch_id)
                .values(scanned_eggs=Batch.scanned_eggs + 1, status="in_progress")
            )
            await db.commit()
        if metadata.temperature is not None or metadata.humidity is not None:
            db.add(
                SensorReading(
                    scan_id=scan.id,
                    device_id=metadata.device_id,
                    temperature=metadata.temperature,
                    humidity=metadata.humidity,
                )
            )
            await db.commit()
        await db.refresh(scan)
        return scan
        
    async def get_scan(self, db: AsyncSession, scan_id: uuid.UUID) -> Scan | None:
        result = await db.execute(select(Scan).filter(Scan.id == scan_id))
        return result.scalar_one_or_none()
        
    async def list_scans(self, db: AsyncSession, page: int = 1, per_page: int = 10, filters: dict = None) -> tuple[list[Scan], int]:
        total_result = await db.execute(select(func.count()).select_from(Scan))
        total = total_result.scalar_one()

        query = (
            select(Scan, Prediction)
            .outerjoin(Prediction, Prediction.scan_id == Scan.id)
            .order_by(Scan.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        result = await db.execute(query)
        items = []
        for scan, prediction in result.all():
            scan.prediction = prediction
            items.append(scan)
        
        return items, total

scan_service = ScanService()
