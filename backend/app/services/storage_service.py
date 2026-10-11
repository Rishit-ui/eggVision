import os
import aiofiles
from app.config import settings

class StorageService:
    def __init__(self):
        self.upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
        os.makedirs(self.upload_dir, exist_ok=True)
    
    async def upload_image(self, file_data: bytes, filename: str, content_type: str) -> str:
        filepath = os.path.join(self.upload_dir, filename)
        async with aiofiles.open(filepath, "wb") as f:
            await f.write(file_data)
        return f"/uploads/{filename}"
        
    async def get_image_url(self, filename: str) -> str:
        return f"/uploads/{filename}"
        
    async def delete_image(self, filename: str) -> bool:
        filepath = os.path.join(self.upload_dir, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False

storage_service = StorageService()
