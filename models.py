"""
models.py — Tablas de Nutri-IA.

  users             → identidad seudonimizada (hash para buscar, número cifrado para escribir)
  health_profiles   → medidas cifradas en reposo + elecciones del Flexi-Menú
  guide_plans       → guía calculada (cifrada)
  weekly_checkins   → peso semanal (cifrado) y veredicto
  payments          → cobros Stripe (Canal 1 y Canal 2)
  professionals     → red B2B (Canal 2)
  processed_events  → idempotencia de webhooks (WhatsApp y Stripe reintentan)
  consent_records   → aceptaciones legales      (SOLO INSERTAR; la BD bloquea cambios)
  audit_log         → bitácora de eventos       (SOLO INSERTAR; la BD bloquea cambios)

Regla: ningún dato sensible se guarda en claro ni en audit_log.detail.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DDL, BigInteger, Boolean, DateTime, Enum, ForeignKey, Index, Integer,
    SmallInteger, String, Text, event, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from crypto import decrypt, encrypt
from database import Base


# ---------------------------------------------------------------------
# Tipos cifrados: se cifran al guardar y se descifran al leer.
# El resto del código asigna y lee valores normales.
# ---------------------------------------------------------------------
class EncryptedText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else encrypt(str(value))

    def process_result_value(self, value, dialect):
        return None if value is None else decrypt(value)


class EncryptedFloat(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else encrypt(repr(float(value)))

    def process_result_value(self, value, dialect):
        return None if value is None else float(decrypt(value))


# ---------------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------------
class Language(str, enum.Enum):
    ES = "es"
    EN = "en"


class Sex(str, enum.Enum):
    FEMALE = "female"
    MALE = "male"


class ActivityLevel(str, enum.Enum):
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    INTENSE = "intense"


class Goal(str, enum.Enum):
    LOSE = "lose"
    MAINTAIN = "maintain"
    GAIN = "gain"


class ConsentType(str, enum.Enum):
    PRIVACY_NOTICE = "privacy_notice"          # Aviso de privacidad / datos sensibles
    EDUCATIONAL_DISCLAIMER = "educational"     # Orientación alimentaria educativa
    SWORN_STATEMENT = "sworn_statement"        # Bajo protesta: patologías graves
    DATA_TRANSFER_B2B = "data_transfer_b2b"    # Reservado para transferencias futuras


class PaymentKind(str, enum.Enum):
    GUIDE = "guide"
    PRO_SUBSCRIPTION = "pro_subscription"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    EXPIRED = "expired"


class ProfessionalStatus(str, enum.Enum):
    REGISTERING = "registering"
    PENDING_VALIDATION = "pending_validation"
    APPROVED_UNPAID = "approved_unpaid"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    REJECTED = "rejected"


def _enum(e: type[enum.Enum], name: str) -> Enum:
    # Guarda el VALOR ("es") y no el nombre ("ES") del enum en PostgreSQL
    return Enum(e, name=name, values_callable=lambda x: [m.value for m in x])


def _created():
    # Hora del SERVIDOR de BD (UTC): no se puede falsear desde el código de la app
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _updated():
    return mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ---------------------------------------------------------------------
# Canal 1 — Usuarios
# ---------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wa_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # pseudonymize_phone()
    wa_phone: Mapped[str] = mapped_column(EncryptedText, nullable=False)      # Cifrado en BD
    alias: Mapped[str | None] = mapped_column(EncryptedText)                  # Cifrado en BD
    language: Mapped[Language | None] = mapped_column(_enum(Language, "language"))
    state: Mapped[str] = mapped_column(String(40), default="START", server_default="START")
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    blocked_reason: Mapped[str | None] = mapped_column(String(40))  # underage | age_over | pathology
    followup_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_checkin_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class HealthProfile(Base):
    """Medidas base. Se llenan paso a paso durante el flujo."""
    __tablename__ = "health_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), unique=True)
    age: Mapped[int | None] = mapped_column(SmallInteger)  # En claro: se usa para filtros de edad
    sex: Mapped[Sex | None] = mapped_column(_enum(Sex, "sex"))
    activity_level: Mapped[ActivityLevel | None] = mapped_column(_enum(ActivityLevel, "activity_level"))
    goal: Mapped[Goal | None] = mapped_column(_enum(Goal, "goal"))
    weight_kg: Mapped[float | None] = mapped_column(EncryptedFloat)
    height_cm: Mapped[float | None] = mapped_column(EncryptedFloat)
    waist_cm: Mapped[float | None] = mapped_column(EncryptedFloat)
    food_choices: Mapped[dict] = mapped_column(JSONB, default=dict)  # Códigos de alimentos (no sensibles)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class GuidePlan(Base):
    """Guía calculada tras el pago. Se cifra porque deriva de datos de salud."""
    __tablename__ = "guide_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    plan: Mapped[str] = mapped_column(EncryptedText)  # JSON del cálculo
    created_at: Mapped[datetime] = _created()


class WeeklyCheckin(Base):
    __tablename__ = "weekly_checkins"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    weight_kg: Mapped[float] = mapped_column(EncryptedFloat)
    verdict: Mapped[str] = mapped_column(String(20))  # celebrate | scold | stall | fast_loss | hold | off_target
    created_at: Mapped[datetime] = _created()


# ---------------------------------------------------------------------
# Canal 2 — Profesionistas
# ---------------------------------------------------------------------
class Professional(Base):
    __tablename__ = "professionals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wa_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    wa_phone: Mapped[str] = mapped_column(EncryptedText, nullable=False)
    language: Mapped[Language] = mapped_column(_enum(Language, "language"))
    state: Mapped[str] = mapped_column(String(30), default="PRO_NAME")
    status: Mapped[ProfessionalStatus] = mapped_column(
        _enum(ProfessionalStatus, "professional_status"), default=ProfessionalStatus.REGISTERING
    )
    full_name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(254))
    city: Mapped[str | None] = mapped_column(String(80), index=True)  # Normalizada (sin acentos, minúsculas)
    cedula: Mapped[str | None] = mapped_column(String(12))
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64))
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


# ---------------------------------------------------------------------
# Pagos e idempotencia
# ---------------------------------------------------------------------
class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[PaymentKind] = mapped_column(_enum(PaymentKind, "payment_kind"))
    status: Mapped[PaymentStatus] = mapped_column(_enum(PaymentStatus, "payment_status"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    professional_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("professionals.id", ondelete="RESTRICT"), index=True
    )
    stripe_session_id: Mapped[str] = mapped_column(String(255), unique=True)
    checkout_url: Mapped[str] = mapped_column(Text)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str | None] = mapped_column(String(3))
    amount_total: Mapped[int | None] = mapped_column(Integer)  # En centavos
    invoice_requested: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = _created()
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProcessedEvent(Base):
    """Evita procesar dos veces el mismo mensaje o evento (los webhooks se reintentan)."""
    __tablename__ = "processed_events"

    source: Mapped[str] = mapped_column(String(20), primary_key=True)     # whatsapp | stripe
    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    created_at: Mapped[datetime] = _created()


# ---------------------------------------------------------------------
# Auditoría (inmutable)
# ---------------------------------------------------------------------
class ConsentRecord(Base):
    """Evidencia legal. Cada aceptación es una fila nueva; nunca se edita."""
    __tablename__ = "consent_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    consent_type: Mapped[ConsentType] = mapped_column(_enum(ConsentType, "consent_type"))
    document_version: Mapped[str] = mapped_column(String(20))   # DISCLAIMER_VERSION
    language: Mapped[Language] = mapped_column(_enum(Language, "language"))
    text_sha256: Mapped[str] = mapped_column(String(64))        # Huella del texto exacto mostrado
    response: Mapped[str] = mapped_column(String(20))           # ACCEPTED | DECLINED | YES | NO
    wa_message_id: Mapped[str | None] = mapped_column(String(128))  # ID del mensaje de WhatsApp
    recorded_at: Mapped[datetime] = _created()

    __table_args__ = (Index("ix_consent_user_type", "user_id", "consent_type"),)


class AuditLog(Base):
    """Bitácora de eventos. detail NUNCA lleva datos sensibles."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()


# ---------------------------------------------------------------------
# Inmutabilidad a nivel PostgreSQL: aunque haya un bug en el código,
# la BD rechaza UPDATE, DELETE y TRUNCATE en las tablas de auditoría.
# Todo es idempotente (CREATE OR REPLACE): se puede ejecutar en cada arranque.
# ---------------------------------------------------------------------
event.listen(
    Base.metadata,
    "after_create",
    DDL(
        """
        CREATE OR REPLACE FUNCTION nutri_block_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Tabla de auditoría inmutable: %% no permitido en %%',
                TG_OP, TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql
        """
    ),
)

for _table in ("consent_records", "audit_log"):
    event.listen(
        Base.metadata,
        "after_create",
        DDL(
            f"CREATE OR REPLACE TRIGGER trg_{_table}_no_mutation "
            f"BEFORE UPDATE OR DELETE ON {_table} "
            f"FOR EACH ROW EXECUTE FUNCTION nutri_block_mutation()"
        ),
    )
    event.listen(
        Base.metadata,
        "after_create",
        DDL(
            f"CREATE OR REPLACE TRIGGER trg_{_table}_no_truncate "
            f"BEFORE TRUNCATE ON {_table} "
            f"FOR EACH STATEMENT EXECUTE FUNCTION nutri_block_mutation()"
        ),
    )
