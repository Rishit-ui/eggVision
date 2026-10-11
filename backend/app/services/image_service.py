import io
from PIL import Image
from app.config import settings

class ImageService:
    def validate_image(self, file_data: bytes) -> tuple[bool, str]:
        if len(file_data) > settings.UPLOAD_MAX_SIZE_MB * 1024 * 1024:
            return False, "File too large"
        try:
            img = Image.open(io.BytesIO(file_data))
            img.verify()
            return True, "Valid image"
        except Exception:
            return False, "Invalid image format"
            
    def get_image_info(self, file_data: bytes) -> dict:
        try:
            img = Image.open(io.BytesIO(file_data))
            return {
                "width": img.width,
                "height": img.height,
                "format": img.format,
                "size": len(file_data)
            }
        except Exception:
            return {}

image_service = ImageService()
