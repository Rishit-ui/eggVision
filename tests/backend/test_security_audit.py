"""Security audit test suite covering authentication, authorization, CORS, rate limiting, and input validation."""

import pytest
from app.config import Settings
from app.middleware.auth import hash_password
from app.middleware.rate_limit import SlidingWindowRateLimiter, get_client_ip
from app.models.user import User
from app.services.image_service import image_service
from app.services.storage_service import StorageService
from fastapi import HTTPException
from httpx import AsyncClient


def test_cors_rejects_wildcard_domains() -> None:
    """Ensure wildcards in domain names (e.g. *.vercel.app) are strictly rejected."""
    with pytest.raises(ValueError, match="must not use wildcard|must not contain wildcard"):
        Settings(CORS_ORIGINS="https://*.vercel.app")

    with pytest.raises(ValueError, match="must not use wildcard|must not contain wildcard"):
        Settings(CORS_ORIGINS="https://*.onrender.com")

    with pytest.raises(ValueError, match="must not use wildcard"):
        Settings(CORS_ORIGINS="*")


def test_cors_accepts_explicit_domains() -> None:
    settings = Settings(CORS_ORIGINS="https://egg-vision.vercel.app, http://localhost:3000")
    assert settings.cors_origins == ["https://egg-vision.vercel.app", "http://localhost:3000"]


def test_production_settings_enforces_https_cors() -> None:
    with pytest.raises(ValueError, match="must use https in production"):
        Settings(
            APP_ENV="production",
            DEBUG=False,
            JWT_SECRET="x" * 32,
            BOOTSTRAP_TOKEN="y" * 32,
            AUTH_REQUIRED=True,
            CORS_ORIGINS="http://egg-vision.vercel.app",
        )


def test_client_ip_extraction_from_x_forwarded_for() -> None:
    class DummyRequest:
        def __init__(self, headers: dict, host: str = "10.0.0.1"):
            self.headers = headers
            self.client = type("Client", (), {"host": host})()

    req = DummyRequest({"x-forwarded-for": "203.0.113.195, 70.41.3.18, 150.172.238.178"})
    assert get_client_ip(req) == "203.0.113.195"

    req_no_header = DummyRequest({}, host="192.168.1.50")
    assert get_client_ip(req_no_header) == "192.168.1.50"


@pytest.mark.asyncio
async def test_sliding_window_rate_limiter() -> None:
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=10)
    key = "test-client-ip"

    await limiter.check(key)
    await limiter.check(key)
    await limiter.check(key)

    with pytest.raises(HTTPException) as exc_info:
        await limiter.check(key)
    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers


@pytest.mark.asyncio
async def test_admin_authorization_on_admin_users(client: AsyncClient) -> None:
    import uuid

    from app.database import get_db
    from app.main import app
    from app.middleware.auth import get_current_user

    admin_user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        password_hash=hash_password("adminpass1234"),
        full_name="System Admin",
        role="admin",
        is_active=True,
    )
    viewer_user = User(
        id=uuid.uuid4(),
        email="viewer@example.com",
        password_hash=hash_password("viewerpass1234"),
        full_name="Regular Viewer",
        role="viewer",
        is_active=True,
    )

    class MockExecuteResult:
        def scalars(self):
            class _Scalars:
                def all(self):
                    return [admin_user, viewer_user]
            return _Scalars()

    class MockDbSession:
        async def execute(self, *args, **kwargs):
            return MockExecuteResult()

    async def mock_get_db():
        yield MockDbSession()

    app.dependency_overrides[get_db] = mock_get_db

    try:
        # 1. Anonymous request (no user) -> 401
        async def mock_anon_user():
            return None

        app.dependency_overrides[get_current_user] = mock_anon_user
        resp_anon = await client.get("/api/v1/admin/users")
        assert resp_anon.status_code == 401

        # 2. Viewer role request -> 403 Forbidden
        async def mock_viewer_user():
            return viewer_user

        app.dependency_overrides[get_current_user] = mock_viewer_user
        resp_viewer = await client.get("/api/v1/admin/users")
        assert resp_viewer.status_code == 403
        assert resp_viewer.json()["detail"] == "Insufficient administrative permissions"

        # 3. Admin role request -> 200 OK
        async def mock_admin_user():
            return admin_user

        app.dependency_overrides[get_current_user] = mock_admin_user
        resp_admin = await client.get("/api/v1/admin/users")
        assert resp_admin.status_code == 200
        users = resp_admin.json()
        assert any(u["email"] == "admin@example.com" for u in users)

    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_health_liveness_and_readiness(client: AsyncClient) -> None:
    from app.database import get_db
    from app.main import app

    # Liveness probe always succeeds
    resp_live = await client.get("/api/v1/health/live")
    assert resp_live.status_code == 200
    assert resp_live.json() == {"status": "alive"}

    # Readiness probe: when database is ready, returns 200
    class ReadyDb:
        async def execute(self, *args, **kwargs):
            return None

    async def mock_ready_db():
        yield ReadyDb()

    app.dependency_overrides[get_db] = mock_ready_db
    try:
        resp_ready = await client.get("/api/v1/health/ready")
        assert resp_ready.status_code == 200
        assert resp_ready.json()["status"] == "ready"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_storage_path_traversal_prevention() -> None:
    for invalid_key in (
        "../secret.txt",
        "..\\secret.txt",
        "uploads/../../etc/passwd",
        "uploads/./file.png",
        "",
        "   ",
    ):
        with pytest.raises(ValueError, match="Invalid storage object key"):
            StorageService._safe_key(invalid_key)

    assert StorageService._safe_key("uploads/user1/image.jpg") == "uploads/user1/image.jpg"


def test_image_service_upload_validation() -> None:
    oversized = b"0" * (21 * 1024 * 1024)
    is_valid, msg = image_service.validate_image(oversized)
    assert is_valid is False
    assert msg == "File too large"

    corrupted = b"NotAnImageHeaderData"
    is_valid, msg = image_service.validate_image(corrupted)
    assert is_valid is False
    assert msg == "Invalid image format"
