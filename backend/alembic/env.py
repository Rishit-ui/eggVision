import asyncio
import os
import sys
from logging.config import fileConfig

# Ensure the repository root and backend directory are on PYTHONPATH.
# This sys.path manipulation must precede the app imports below; the noqa
# comments silence ruff E402 (module-level import not at top of file) which
# would otherwise flag the deferred imports as style violations.
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
backend_path = os.path.join(repo_root, 'backend')
if repo_root not in sys.path:
    sys.path.append(repo_root)
if backend_path not in sys.path:
    sys.path.append(backend_path)

from alembic import context  # noqa: E402
from app.config import settings  # noqa: E402
from app.models.base import Base  # noqa: E402
from sqlalchemy import pool  # noqa: E402
from sqlalchemy.ext.asyncio import async_engine_from_config  # noqa: E402

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    connect_args = {}
    db_url = config.get_main_option("sqlalchemy.url") or ""
    if ":6543" in db_url or "pooler" in db_url.lower():
        connect_args["statement_cache_size"] = 0

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
