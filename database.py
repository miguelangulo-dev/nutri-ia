"""
database.py — Conexión asíncrona a PostgreSQL (Railway) con SQLAlchemy 2.0.

Asíncrona porque el bot recibe webhooks de WhatsApp y Stripe en paralelo:
mientras una consulta espera a la BD, el servidor atiende otros mensajes.

Dependencias:  pip install "sqlalchemy[asyncio]>=2.0" asyncpg
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import get_settings


def _async_url(raw: str) -> str:
    """Railway entrega 'postgresql://...' o 'postgres://...';
    el driver asíncrono necesita 'postgresql+asyncpg://...'."""
    for prefix in ("postgresql://", "postgres://"):
        if raw.startswith(prefix):
            return "postgresql+asyncpg://" + raw[len(prefix):]
    return raw


class Base(DeclarativeBase):
    """Clase base de todas las tablas."""


engine = create_async_engine(
    _async_url(get_settings().database_url.get_secret_value()),
    pool_size=5,         # Conexiones abiertas de forma permanente
    max_overflow=5,      # Extra en picos de tráfico
    pool_pre_ping=True,  # Detecta conexiones caídas antes de usarlas
    pool_recycle=1800,   # Renueva conexiones cada 30 min
    echo=False,          # True solo para depurar: imprime el SQL
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Unidad de trabajo: confirma todo si sale bien, revierte todo si falla.

    Uso:
        async with get_session() as s:
            s.add(objeto)
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Crea tablas y triggers de inmutabilidad si no existen.
    Fase 1. Cuando el esquema empiece a cambiar, migrar con Alembic."""
    import models  # noqa: F401  (registra las tablas en Base.metadata)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
