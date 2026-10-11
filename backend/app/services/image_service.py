import io
from PIL import Image
from app.config import settings

class ImageService:
    ALLOWED_FORMATS = {"JPEG": ("image/jpeg", ".jpg"), "PNG": ("image/png", ".png"), "WEBP": ("image/webp", ".webp")}

    def validate_image(self, file_data: bytes) -> tuple[bool, str]:
        if len(file_data) > settings.UPLOAD_MAX_SIZE_MB * 1024 * 1024:
            return False, "File too large"
        try:
            with Image.open(io.BytesIO(file_data)) as img:
                if img.format not in self.ALLOWED_FORMATS:
                    return False, "Unsupported image format. Upload a JPEG, PNG, or WebP image."
                if img.width * img.height > settings.UPLOAD_MAX_PIXELS:
                    return False, "Image dimensions are too large"
                img.load()
            return True, "Valid image"
        except Exception:
            return False, "Invalid image format"

    def canonical_upload_details(self, file_data: bytes) -> tuple[str, str]:
        """Return server-derived MIME type and extension; never trust a client filename."""
        with Image.open(io.BytesIO(file_data)) as img:
            return self.ALLOWED_FORMATS[img.format]
            
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
