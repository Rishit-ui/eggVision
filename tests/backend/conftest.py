import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

@pytest.fixture
def app():
    """Use the actual application; endpoint tests must never target a fake app."""
    from app.main import app as eggvision_app
    return eggvision_app

@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
