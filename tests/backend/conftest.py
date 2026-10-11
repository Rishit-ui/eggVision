import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

@pytest.fixture
def app():
    # Placeholder for actual FastAPI app import
    from fastapi import FastAPI
    app = FastAPI()
    
    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}
        
    @app.post("/api/v1/scan")
    async def scan():
        return {"id": "123", "status": "created"}
        
    @app.post("/api/v1/predict")
    async def predict():
        return {"status": "model_not_ready"}
        
    return app

@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
