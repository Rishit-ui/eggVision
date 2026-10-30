import inspect
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import Headers

from app.config import Settings
from app.routers import health


def production_settings(**overrides):
    values = {
        "APP_ENV": "production",
        "DEBUG": False,
        "JWT_SECRET": "a" * 32,
        "BOOTSTRAP_TOKEN": "b" * 32,
        "AUTH_REQUIRED": True,
        "CORS_ORIGINS": "https://egg-vision.vercel.app",
    }
    values.update(overrides)
    return Settings(**values)


def test_production_accepts_render_origin_without_object_storage() -> None:
    settings = production_settings()
    assert settings.cors_origins == ["https://egg-vision.vercel.app"]
    assert settings.S3_REQUIRED is False


def test_production_rejects_wildcard_cors() -> None:
    with pytest.raises(ValueError, match="must not use wildcard"):
        production_settings(CORS_ORIGINS="*")


def test_production_cors_preflight_allows_authorization_header() -> None:
    middleware = CORSMiddleware(
        app=lambda scope, receive, send: None,
        allow_origins=production_settings().cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    response = middleware.preflight_response(Headers({
        "Origin": "https://egg-vision.vercel.app",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    }))
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://egg-vision.vercel.app"


def test_migration_graph_contains_the_complete_initial_schema() -> None:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "backend" / "alembic.ini"))
    config.set_main_option("script_location", str(root / "backend" / "alembic"))
    script = ScriptDirectory.from_config(config)
    revisions = list(script.walk_revisions(base="base", head="heads"))
    assert [revision.revision for revision in revisions] == ["001_initial_schema"]
    source = (root / "backend" / "alembic" / "versions" / "001_initial_schema.py").read_text(encoding="utf-8")
    for table in ("users", "batches", "scans", "predictions", "sensor_readings", "ground_truth"):
        assert f"create_table('{table}'" in source


def test_redis_health_client_cleanup_is_guaranteed() -> None:
    source = inspect.getsource(health.health_check)
    assert "finally:" in source
    assert "await client.aclose()" in source

