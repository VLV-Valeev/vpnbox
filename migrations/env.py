"""Alembic migration environment — async вариант под asyncpg.

Главные отличия от дефолта:
  1. `sqlalchemy.url` берётся динамически из `settings.database_url`
     (из `.env` через pydantic-settings) — ничего не хардкодим в alembic.ini.
  2. Используется `create_async_engine` и `connection.run_sync`, потому что
     наш основной движок — asyncpg.
  3. Все модели импортируются одним махом (`from app.db import models`)
     — чтобы `target_metadata` увидел каждую таблицу при --autogenerate.
  4. `compare_type=True` + `compare_server_default=True` — Alembic замечает
     изменения типов колонок и дефолтов, а не только добавление/удаление.
"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Настройки проекта и метаданные моделей
from app.config import settings
from app.db.models import Base

# КРИТИЧЕСКИ ВАЖНО: импортируем все модули с SQLAlchemy-моделями. Каждый
# импорт регистрирует свои таблицы в `Base.metadata`, и только после этого
# `--autogenerate` увидит их при diff'е. Сейчас все модели лежат в одном
# файле, но если добавятся новые — просто допиши импорт сюда.
from app.db import models  # noqa: F401

# Alembic config object — даёт доступ к alembic.ini
config = context.config

# Подставляем URL из settings (не из alembic.ini).
# Экранируем %, чтобы alembic не интерпретировал его как подстановку.
config.set_main_option(
    "sqlalchemy.url",
    settings.database_url.replace("%", "%%"),
)

# Подключаем logging из alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Целевые метаданные, с которыми сравнивается текущее состояние БД
target_metadata = Base.metadata


def _do_run_migrations(connection: Connection) -> None:
    """Запуск миграций на синхронном коннекшне (создаётся из async через run_sync)."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,             # ловить изменения типов колонок
        compare_server_default=True,   # ловить изменения DEFAULT
        render_as_batch=False,         # True нужен только для SQLite
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_migrations_online_async() -> None:
    """Online-режим: подключаемся к реальной БД и применяем/генерируем."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(_run_migrations_online_async())


def run_migrations_offline() -> None:
    """Offline-режим: генерируем SQL-скрипт без подключения (для артефактов)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
