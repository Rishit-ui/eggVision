from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://eggvision:eggvision@localhost:5432/eggvision"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    S3_ENDPOINT: str | None = None
    S3_BUCKET: str | None = None
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None
    S3_REQUIRED: bool = False
    
    # A development-only value. Production startup is blocked if this is not replaced.
    JWT_SECRET: str = "development-only-change-me-before-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60
    AUTH_REQUIRED: bool = False
    BOOTSTRAP_TOKEN: str | None = None
    
    MODEL_PATH: str | None = None
    INFERENCE_DEVICE: str = "cpu"
    
    APP_ENV: str = "development"
    DEBUG: bool = True
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"
    CORS_ORIGINS: str = "http://localhost:3000"
    
    UPLOAD_MAX_SIZE_MB: int = 10
    UPLOAD_MAX_PIXELS: int = 25_000_000
    
    model_config = SettingsConfigDict(env_file=".env")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.APP_ENV.lower() == "production":
            insecure_secret = self.JWT_SECRET == "development-only-change-me-before-production"
            if insecure_secret or len(self.JWT_SECRET) < 32:
                raise ValueError("JWT_SECRET must be a unique value of at least 32 characters in production")
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production")
            if not self.cors_origins or any(origin == "*" for origin in self.cors_origins):
                raise ValueError("CORS_ORIGINS must explicitly list trusted origins in production")
            if not self.AUTH_REQUIRED:
                raise ValueError("AUTH_REQUIRED must be true in production")
            if not self.BOOTSTRAP_TOKEN or len(self.BOOTSTRAP_TOKEN) < 32:
                raise ValueError("BOOTSTRAP_TOKEN must be a unique value of at least 32 characters in production")
            if not self.S3_REQUIRED or not all((self.S3_ENDPOINT, self.S3_BUCKET, self.S3_ACCESS_KEY, self.S3_SECRET_KEY)):
                raise ValueError("S3-compatible object storage must be configured in production")
        return self

settings = Settings()
