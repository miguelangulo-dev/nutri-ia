"""
checkin.py — Seguimiento semanal.

Dos partes:
1. run_weekly_checkins(): tarea programada. Envía la plantilla aprobada por
   Meta a quien le toca su check-in (fuera de la ventana de 24 h WhatsApp
   solo permite plantillas). En Railway se ejecuta como servicio Cron con:
       python checkin.py
2. process_checkin(): cuando el usuario responde con su peso, se evalúa y el
   bot responde con su personalidad.

Regla de seguridad: una bajada ≥1.5 % del peso en una semana NUNCA se
celebra; se trata como alerta, sin importar la meta.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from audit import log_event
from config import get_settings
from database import get_session
from messages import t
from models import Goal, HealthProfile, Language, User, WeeklyCheckin
from states import S, parse_number
from whatsapp import Inbound, Out, WhatsAppClient, text

log = logging.getLogger("nutri.checkin")

FAST_LOSS_PCT = -1.5   # % de peso por semana
NOISE_KG = 0.2         # Variación que se considera "sin cambio"


def evaluate(goal: Goal, prev: float, new: float) -> str:
    delta = new - prev
    pct = delta / prev * 100
    if pct <= FAST_LOSS_PCT:
        return "fast_loss"
    if goal == Goal.MAINTAIN:
        return "hold" if abs(delta) <= 0.5 else "off_target"
    toward = -delta if goal == Goal.LOSE else delta   # Positivo = hacia la meta
    if toward >= NOISE_KG:
        return "celebrate"
    if toward <= -NOISE_KG:
        return "scold"
    return "stall"


async def process_checkin(session: AsyncSession, user: User, profile: HealthProfile,
                          inb: Inbound, lang: str) -> list[Out]:
    weight = parse_number(inb.text)
    if weight is None or not 30 <= weight <= 300:
        return [text(t("invalid_range", lang, lo=30, hi=300, unit="kg"))]

    last = await session.scalar(
        select(WeeklyCheckin).where(WeeklyCheckin.user_id == user.id)
        .order_by(WeeklyCheckin.created_at.desc()).limit(1)
    )
    prev = last.weight_kg if last else profile.weight_kg
    verdict = evaluate(profile.goal, prev, weight)

    session.add(WeeklyCheckin(user_id=user.id, weight_kg=weight, verdict=verdict))
    user.state = S.ACTIVE
    log_event(session, "checkin.done", user.id, verdict=verdict)
    return [text(t(f"checkin_{verdict}", lang, alias=user.alias or "", delta=abs(weight - prev)))]


async def run_weekly_checkins() -> None:
    s = get_settings()
    now = datetime.now(timezone.utc)
    client = WhatsAppClient()
    sent = 0
    try:
        async with get_session() as session:
            due = (await session.scalars(
                select(User.id).where(
                    User.state == S.ACTIVE,
                    User.is_blocked.is_(False),
                    User.next_checkin_at <= now,
                )
            )).all()

        for user_id in due:
            try:
                # Una transacción por usuario: si falla uno, los demás siguen
                async with get_session() as session:
                    user = await session.get(User, user_id, with_for_update=True)
                    if user.followup_until and user.followup_until <= now:
                        user.state = S.FINISHED
                        user.next_checkin_at = None
                        log_event(session, "followup.finished", user.id)
                        continue
                    en = user.language == Language.EN
                    await client.send(user.wa_phone, Out(
                        "template",
                        template=s.wa_template_checkin_en if en else s.wa_template_checkin_es,
                        template_lang=s.wa_template_lang_en if en else s.wa_template_lang_es,
                    ))
                    user.state = S.CHECKIN_WEIGHT
                    user.next_checkin_at = now + timedelta(days=7)
                    log_event(session, "checkin.sent", user.id)
                    sent += 1
            except Exception:
                log.exception("Fallo el check-in de un usuario (id interno %s)", user_id)
    finally:
        await client.aclose()
    log.info("Check-ins enviados: %s", sent)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_weekly_checkins())
