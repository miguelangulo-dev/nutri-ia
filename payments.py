"""
payments.py — Cobros con Stripe.

Canal 1: Checkout en modo "payment" (pago único). MXN si el usuario eligió
español, USD si eligió inglés. Los montos ($299 MXN y su equivalente) se
configuran en el Dashboard de Stripe; aquí solo se usan los price_... IDs.

Canal 2: Checkout en modo "subscription" (Stripe Billing, mensual).

Webhook: se verifica la firma, se descarta cualquier evento repetido
(idempotencia) y la guía se calcula y entrega SOLO cuando Stripe confirma
el pago. El usuario se identifica con su UUID, nunca con su teléfono.

CFDI 4.0: Stripe captura el RFC (tax_id_collection) pero NO timbra.
Mientras se conecta un PAC, la solicitud queda registrada en auditoría y el
usuario recibe instrucciones para completar sus datos fiscales.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from audit import claim_event, log_event
from config import get_settings
from database import get_session
from messages import t
from models import (
    GuidePlan, HealthProfile, Language, Payment, PaymentKind, PaymentStatus,
    Professional, ProfessionalStatus, Sex, User,
)
from nutrition import Plan, calculate, render
from states import P, S
from whatsapp import Out, text

log = logging.getLogger("nutri.payments")

Notification = tuple[str, Out]  # (teléfono destino, mensaje)


class InvalidStripeSignature(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _locale(lang: Language | None) -> str:
    return "en" if lang == Language.EN else "es-419"


async def _create_checkout(**params) -> tuple[str, str]:
    """Llama a Stripe en un hilo aparte para no bloquear el servidor."""
    stripe.api_key = get_settings().stripe_secret_key.get_secret_value()
    cs = await asyncio.to_thread(stripe.checkout.Session.create, **params)
    return cs["id"], cs["url"]


async def guide_checkout_url(session: AsyncSession, user: User) -> str:
    """Reutiliza un enlace pendiente reciente (<23 h; Stripe los expira a las 24 h)
    o crea uno nuevo."""
    recent = await session.scalar(
        select(Payment)
        .where(
            Payment.user_id == user.id,
            Payment.kind == PaymentKind.GUIDE,
            Payment.status == PaymentStatus.PENDING,
            Payment.created_at > _now() - timedelta(hours=23),
        )
        .order_by(Payment.created_at.desc())
        .limit(1)
    )
    if recent:
        return recent.checkout_url

    s = get_settings()
    en = user.language == Language.EN
    session_id, url = await _create_checkout(
        mode="payment",
        line_items=[{"price": s.stripe_price_guide_usd if en else s.stripe_price_guide_mxn, "quantity": 1}],
        client_reference_id=str(user.id),
        metadata={"kind": "guide", "user_id": str(user.id)},
        success_url=s.stripe_success_url,
        cancel_url=s.stripe_cancel_url,
        locale=_locale(user.language),
        customer_creation="always",
        tax_id_collection={"enabled": True},  # Permite capturar RFC para CFDI
    )
    session.add(Payment(
        id=uuid.uuid4(), kind=PaymentKind.GUIDE, status=PaymentStatus.PENDING,
        user_id=user.id, stripe_session_id=session_id, checkout_url=url,
    ))
    return url


async def expire_pending_guide_links(session: AsyncSession, user: User) -> None:
    """Invalida en Stripe los enlaces de pago pendientes del usuario (comando CANCELAR),
    para que no pueda pagar una guía de un flujo que ya abandonó."""
    pending = (await session.scalars(
        select(Payment).where(
            Payment.user_id == user.id,
            Payment.kind == PaymentKind.GUIDE,
            Payment.status == PaymentStatus.PENDING,
        )
    )).all()
    if not pending:
        return
    stripe.api_key = get_settings().stripe_secret_key.get_secret_value()
    for pay in pending:
        try:
            await asyncio.to_thread(stripe.checkout.Session.expire, pay.stripe_session_id)
        except Exception:
            # Ya expirado o ya pagado: el webhook de Stripe decide el estado final
            log.warning("No se pudo expirar la sesión de pago %s", pay.id)
        pay.status = PaymentStatus.EXPIRED


async def pro_checkout_url(session: AsyncSession, pro: Professional) -> str:
    s = get_settings()
    en = pro.language == Language.EN
    meta = {"kind": "pro", "professional_id": str(pro.id)}
    session_id, url = await _create_checkout(
        mode="subscription",
        line_items=[{"price": s.stripe_price_pro_usd if en else s.stripe_price_pro_mxn, "quantity": 1}],
        client_reference_id=str(pro.id),
        metadata=meta,
        subscription_data={"metadata": meta},
        success_url=s.stripe_success_url,
        cancel_url=s.stripe_cancel_url,
        locale=_locale(pro.language),
        tax_id_collection={"enabled": True},
    )
    session.add(Payment(
        id=uuid.uuid4(), kind=PaymentKind.PRO_SUBSCRIPTION, status=PaymentStatus.PENDING,
        professional_id=pro.id, stripe_session_id=session_id, checkout_url=url,
    ))
    return url


# ---------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------
async def handle_stripe_event(raw: bytes, signature: str) -> list[Notification]:
    s = get_settings()
    try:
        stripe.Webhook.construct_event(raw, signature, s.stripe_webhook_secret.get_secret_value())
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise InvalidStripeSignature from exc

    event = json.loads(raw)  # Ya verificado; se usa como dict simple
    etype = event["type"]
    obj = event["data"]["object"]

    async with get_session() as session:
        if not await claim_event(session, "stripe", event["id"]):
            return []  # Evento repetido: ya se procesó

        if etype in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            kind = (obj.get("metadata") or {}).get("kind")
            if kind == "guide":
                return await _fulfill_guide(session, obj)
            if kind == "pro":
                return await _activate_pro(session, obj)
        elif etype == "checkout.session.expired":
            pay = await session.scalar(select(Payment).where(Payment.stripe_session_id == obj["id"]))
            if pay and pay.status == PaymentStatus.PENDING:
                pay.status = PaymentStatus.EXPIRED
        elif etype in ("invoice.paid", "invoice.payment_failed"):
            return await _pro_invoice(session, obj, paid=etype == "invoice.paid")
        elif etype == "customer.subscription.deleted":
            return await _pro_canceled(session, obj["id"])
    return []


async def _fulfill_guide(session: AsyncSession, obj: dict) -> list[Notification]:
    if obj.get("payment_status") != "paid":
        return []  # Pagos diferidos (ej. OXXO) llegan después como async_payment_succeeded

    pay = await session.scalar(
        select(Payment).where(Payment.stripe_session_id == obj["id"]).with_for_update()
    )
    if not pay or pay.status == PaymentStatus.PAID:
        return []

    s = get_settings()
    pay.status = PaymentStatus.PAID
    pay.paid_at = _now()
    pay.amount_total = obj.get("amount_total")
    pay.currency = obj.get("currency")
    pay.stripe_customer_id = obj.get("customer")
    pay.invoice_requested = bool((obj.get("customer_details") or {}).get("tax_ids"))

    user = await session.get(User, pay.user_id, with_for_update=True)
    profile = await session.scalar(select(HealthProfile).where(HealthProfile.user_id == user.id))
    lang = (user.language or Language.ES).value

    plan = calculate(
        sex=profile.sex.value,
        age=profile.age,
        weight_kg=profile.weight_kg,
        height_cm=profile.height_cm,
        waist_cm=profile.waist_cm,
        activity=profile.activity_level.value,
        goal=profile.goal.value,
        choices=profile.food_choices or {},
        kcal_floor=s.min_daily_kcal_male if profile.sex == Sex.MALE else s.min_daily_kcal_female,
    )
    session.add(GuidePlan(user_id=user.id, plan=json.dumps(plan.__dict__)))

    user.state = S.ACTIVE
    user.followup_until = _now() + timedelta(weeks=s.followup_weeks)
    user.next_checkin_at = _now() + timedelta(days=7)
    log_event(session, "payment.guide_paid", user.id, payment_id=str(pay.id), kcal=plan.kcal)

    phone = user.wa_phone
    notes = [(phone, text(t("payment_ok", lang))), (phone, text(render(plan, lang, user.alias)))]
    if pay.invoice_requested:
        log_event(session, "invoice.requested", user.id, payment_id=str(pay.id))
        notes.append((phone, text(t("invoice_pending", lang, email=s.support_email,
                                    folio=str(pay.id)[:8].upper()))))
    return notes


def load_plan(raw_json: str) -> Plan:
    return Plan(**json.loads(raw_json))


async def _activate_pro(session: AsyncSession, obj: dict) -> list[Notification]:
    pro_id = (obj.get("metadata") or {}).get("professional_id")
    if not pro_id:
        return []
    pro = await session.get(Professional, uuid.UUID(pro_id), with_for_update=True)
    pay = await session.scalar(select(Payment).where(Payment.stripe_session_id == obj["id"]))
    if not pro:
        return []
    if pay and pay.status != PaymentStatus.PAID:
        pay.status = PaymentStatus.PAID
        pay.paid_at = _now()
        pay.amount_total = obj.get("amount_total")
        pay.currency = obj.get("currency")
        pay.stripe_customer_id = obj.get("customer")
    pro.stripe_customer_id = obj.get("customer")
    pro.stripe_subscription_id = obj.get("subscription")
    pro.status = ProfessionalStatus.ACTIVE
    pro.state = P.WAIT
    log_event(session, "pro.activated", None, professional_id=str(pro.id))
    return [(pro.wa_phone, text(t("pro_active", pro.language.value)))]


def _subscription_id(invoice: dict) -> str | None:
    """Compatible con versiones antiguas y nuevas del API de Stripe."""
    return invoice.get("subscription") or (
        ((invoice.get("parent") or {}).get("subscription_details") or {}).get("subscription")
    )


async def _pro_invoice(session: AsyncSession, invoice: dict, paid: bool) -> list[Notification]:
    sub_id = _subscription_id(invoice)
    if not sub_id:
        return []
    pro = await session.scalar(
        select(Professional).where(Professional.stripe_subscription_id == sub_id).with_for_update()
    )
    if not pro:
        return []  # La primera factura puede llegar antes que checkout.session.completed
    if paid:
        if pro.status == ProfessionalStatus.PAST_DUE:
            pro.status = ProfessionalStatus.ACTIVE
            log_event(session, "pro.reactivated", None, professional_id=str(pro.id))
        return []
    pro.status = ProfessionalStatus.PAST_DUE
    log_event(session, "pro.past_due", None, professional_id=str(pro.id))
    return [(pro.wa_phone, text(t("pro_past_due", pro.language.value)))]


async def _pro_canceled(session: AsyncSession, sub_id: str) -> list[Notification]:
    pro = await session.scalar(
        select(Professional).where(Professional.stripe_subscription_id == sub_id).with_for_update()
    )
    if not pro:
        return []
    pro.status = ProfessionalStatus.CANCELED
    log_event(session, "pro.canceled", None, professional_id=str(pro.id))
    return [(pro.wa_phone, text(t("pro_canceled", pro.language.value)))]
