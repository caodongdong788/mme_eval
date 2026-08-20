from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from server.db import Base
from server import models_db  # noqa: F401


config = context.config
if config.config_file_name is not None:
    # Alembic 默认会禁用所有未在 ini 中声明的业务 logger，导致应用后续告警静默。
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is None:
        raise RuntimeError("MME Alembic migrations require an injected SQLAlchemy connection")
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
