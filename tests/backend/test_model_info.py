import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_get_model_info():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.get('/api/v1/model/info')
        assert response.status_code == 200
        data = response.json()
        assert data['is_ready'] is False
        assert data['description'] == 'no model loaded'

