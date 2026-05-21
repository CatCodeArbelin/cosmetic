from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def _migrate_dialogs_schema(connection) -> None:
    await connection.execute(text('ALTER TABLE dialogs ADD COLUMN IF NOT EXISTS external_user_id BIGINT'))
    await connection.execute(text('ALTER TABLE dialogs ADD COLUMN IF NOT EXISTS client_name VARCHAR(255)'))
    await connection.execute(text('ALTER TABLE dialogs ADD COLUMN IF NOT EXISTS username VARCHAR(255)'))

    await connection.execute(
        text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'dialogs' AND column_name = 'operator_id'
                ) AND NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'dialogs' AND column_name = 'assigned_operator_id'
                ) THEN
                    ALTER TABLE dialogs RENAME COLUMN operator_id TO assigned_operator_id;
                END IF;
            END$$;
            """
        )
    )
    await connection.execute(text('ALTER TABLE dialogs ADD COLUMN IF NOT EXISTS assigned_operator_id BIGINT'))
    await connection.execute(text('DROP INDEX IF EXISTS ix_dialogs_operator_id'))
    await connection.execute(text('CREATE INDEX IF NOT EXISTS ix_dialogs_assigned_operator_id ON dialogs (assigned_operator_id)'))
    await connection.execute(text('ALTER TABLE dialogs DROP COLUMN IF EXISTS title'))


async def init_database(database_url: str) -> None:
    global _engine, _session_factory
    _engine = create_async_engine(database_url, pool_pre_ping=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)

    async with _engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await _migrate_dialogs_schema(connection)


async def close_database() -> None:
    if _engine is not None:
        await _engine.dispose()


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError('Database is not initialized')
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session
