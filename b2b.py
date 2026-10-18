"""
b2b.py — Canal 2: red de profesionistas de la salud (detrás de feature flag).

Flujo: nombre → correo → ciudad → cédula → validación → suscripción Stripe →
activo para recibir derivaciones.

Validación de cédula: la SEP no ofrece una API pública oficial y su portal
usa captcha, así que la validación es MANUAL por defecto (endpoint de
administración en main.py). FF_CEDULA_AUTO_VALIDATION queda listo para
conectar un proveedor de verificación cuando lo contrates.

Derivación: al usuario se le entregan los datos de contacto del
profesionista. Los datos de salud del usuario NO se transfieren.
"""
import logging
import re
import unicodedata
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from audit import log_event
from config import get_settings
from messages import t
from models import Professional, ProfessionalStatus, User
from payments import pro_checkout_url
from states import P, S
from whatsapp import Inbound, Out, text

log = logging.getLogger("nutri.b2b")

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_city(raw: str) -> str:
    """'  San Miguel de Allende ' y 'san miguel de allende' quedan iguales."""
    no_accents = "".join(
        c for c in unicodedata.normalize("NFKD", raw) if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", no_accents).strip().lower()[:80]


def _price(lang: str) -> str:
    s = get_settings()
    return s.pro_price_label_en if lang == "en" else s.pro_price_label_es


async def validate_cedula(cedula: str) -> bool | None:
    """True/False si un proveedor confirma; None = enviar a revisión manual."""
    if get_settings().ff_cedula_auto_validation:
        log.warning("Validación automática de cédula sin proveedor conectado: pasa a revisión manual")
    return None


async def start_registration(session: AsyncSession, user: User) -> list[Out]:
    """Convierte un número entrante en registro de profesionista."""
    pro = await session.scalar(select(Professional).where(Professional.wa_hash == user.wa_hash))
    if pro is None:
        pro = Professional(
            id=uuid.uuid4(), wa_hash=user.wa_hash, wa_phone=user.wa_phone,
            language=user.language, state=P.NAME, status=ProfessionalStatus.REGISTERING,
        )
        session.add(pro)
    return [text(t("pro_ask_name", pro.language.value))]


async def handle_pro(session: AsyncSession, pro: Professional, inb: Inbound) -> list[Out]:
    s = get_settings()
    lang = pro.language.value
    ans = inb.text.strip()

    if pro.state == P.NAME:
        if len(ans) < 5:
            return [text(t("pro_ask_name", lang))]
        pro.full_name = ans[:120]
        pro.state = P.EMAIL
        return [text(t("pro_ask_email", lang))]

    if pro.state == P.EMAIL:
        if not _EMAIL.match(ans):
            return [text(t("invalid_email", lang))]
        pro.email = ans.lower()[:254]
        pro.state = P.CITY
        return [text(t("pro_ask_city", lang))]

    if pro.state == P.CITY:
        city = normalize_city(ans)
        if len(city) < 3:
            return [text(t("pro_ask_city", lang))]
        pro.city = city
        pro.state = P.CEDULA
        return [text(t("pro_ask_cedula", lang))]

    if pro.state == P.CEDULA:
        cedula = re.sub(r"\D", "", ans)
        if not 7 <= len(cedula) <= 8:
            return [text(t("invalid_cedula", lang))]
        pro.cedula = cedula
        pro.state = P.WAIT
        pro.status = ProfessionalStatus.PENDING_VALIDATION
        log_event(session, "pro.registered", None, professional_id=str(pro.id))
        if await validate_cedula(cedula):
            pro.status = ProfessionalStatus.APPROVED_UNPAID
        else:
            return [text(t("pro_pending", lang, price=_price(lang)))]

    # --- A partir de aquí decide el estatus ---
    if pro.status == ProfessionalStatus.PENDING_VALIDATION:
        return [text(t("pro_pending", lang, price=_price(lang)))]
    if pro.status in (ProfessionalStatus.APPROVED_UNPAID, ProfessionalStatus.CANCELED):
        url = await pro_checkout_url(session, pro)
        return [text(t("pro_checkout", lang, price=_price(lang), url=url))]
    if pro.status == ProfessionalStatus.ACTIVE:
        return [text(t("pro_active", lang))]
    if pro.status == ProfessionalStatus.PAST_DUE:
        return [text(t("pro_past_due", lang))]
    return [text(t("pro_rejected", lang, email=s.support_email))]


async def approve(session: AsyncSession, pro_id: uuid.UUID) -> tuple[Professional, str] | None:
    """Aprobación manual de cédula. Devuelve el profesionista y su enlace de pago."""
    pro = await session.get(Professional, pro_id, with_for_update=True)
    if not pro or pro.status != ProfessionalStatus.PENDING_VALIDATION:
        return None
    pro.status = ProfessionalStatus.APPROVED_UNPAID
    log_event(session, "pro.approved", None, professional_id=str(pro.id))
    return pro, await pro_checkout_url(session, pro)


async def reject(session: AsyncSession, pro_id: uuid.UUID) -> Professional | None:
    pro = await session.get(Professional, pro_id, with_for_update=True)
    if not pro or pro.status != ProfessionalStatus.PENDING_VALIDATION:
        return None
    pro.status = ProfessionalStatus.REJECTED
    log_event(session, "pro.rejected", None, professional_id=str(pro.id))
    return pro


async def refer_user(session: AsyncSession, user: User, city_text: str, lang: str) -> list[Out]:
    """Busca un profesionista activo en la ciudad del usuario y bloquea la guía."""
    city = normalize_city(city_text)
    if len(city) < 3:
        return [text(t("referral_ask_city", lang))]

    user.is_blocked = True
    user.blocked_reason = "pathology"
    user.state = S.BLOCKED

    pro = await session.scalar(
        select(Professional)
        .where(Professional.status == ProfessionalStatus.ACTIVE, Professional.city == city)
        .order_by(func.random())  # Reparto equitativo entre especialistas de la ciudad
        .limit(1)
    )
    if not pro:
        log_event(session, "referral.no_professional", user.id)
        return [text(t("referral_none", lang)), text(t("pathology_block", lang))]

    log_event(session, "referral.created", user.id, professional_id=str(pro.id))
    digits = re.sub(r"\D", "", pro.wa_phone)
    outs = [text(t("referral_found", lang, name=pro.full_name, email=pro.email,
                   wa=f"https://wa.me/{digits}"))]
    notice = text(t("pro_referral_notice", pro.language.value, city=city_text.strip().title()))
    notice.to = pro.wa_phone
    outs.append(notice)
    return outs
