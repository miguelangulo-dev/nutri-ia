"""
audit.py — Escritura en tablas de auditoría e idempotencia de webhooks.

Solo inserciones: las tablas de auditoría no admiten UPDATE ni DELETE.
"""
import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from crypto import text_fingerprint
from models import AuditLog, ConsentRecord, ConsentType, Language, ProcessedEvent


def log_event(session: AsyncSession, event_type: str, user_id: uuid.UUID | None = None, **detail) -> None:
    """Registra un evento. detail: solo IDs, conteos o códigos, NUNCA datos sensibles."""
    session.add(AuditLog(event_type=event_type, user_id=user_id, detail=detail))


def record_consent(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    consent_type: ConsentType,
    language: Language,
    shown_text: str,
    response: str,
    wa_message_id: str | None,
) -> None:
    """Guarda la evidencia de una aceptación/declaración con la huella SHA-256
    del texto exacto que vio el usuario y la versión vigente del documento."""
    session.add(
        ConsentRecord(
            user_id=user_id,
            consent_type=consent_type,
            document_version=get_settings().disclaimer_version,
            language=language,
            text_sha256=text_fingerprint(shown_text),
            response=response,
            wa_message_id=wa_message_id,
        )
    )


async def claim_event(session: AsyncSession, source: str, event_id: str) -> bool:
    """True si el evento es nuevo (y lo marca como tomado); False si ya se procesó.
    Si la transacción falla después, la marca se revierte y el reintento funciona."""
    stmt = (
        pg_insert(ProcessedEvent)
        .values(source=source, event_id=event_id)
        .on_conflict_do_nothing()
        .returning(ProcessedEvent.event_id)
    )
    return (await session.execute(stmt)).first() is not None
