from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from core.config import Settings
from storage.db.base import Base
import storage.db.models  # noqa: F401 — registers Phase 2 models with Base.metadata

# Adapted from ai-project-control-tower/alembic/env.py (see
# BANKING_PLATFORM_INTEGRATION_PLAN.md §3). storage/db/models/ now exists
# (Phase 2 — scan/file-inventory/domain-mapping/finding/scanner-execution
# tables); target_metadata reflects them starting with revision 0001.

config = context.config
settings = Settings()

if settings.database_url:
    config.set_main_option("sqlalchemy.url", settings.database_url)

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


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
