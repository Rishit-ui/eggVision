from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://eggvision:eggvision@localhost:5432/eggvision"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    S3_ENDPOINT: str | None = None
    S3_BUCKET: str | None = None
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None
    
    JWT_SECRET: str = "supersecret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60
    
    MODEL_PATH: str | None = None
    INFERENCE_DEVICE: str = "cpu"
    
    APP_ENV: str = "development"
    DEBUG: bool = True
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"
    
    UPLOAD_MAX_SIZE_MB: int = 10
    
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
