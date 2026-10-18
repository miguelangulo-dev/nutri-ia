"""
main.py — Servidor web de Nutri-IA (FastAPI).

Rutas:
  GET  /health                                  → Railway verifica que la app vive
  GET  /webhook/whatsapp                        → Verificación del webhook (Meta)
  POST /webhook/whatsapp                        → Mensajes entrantes
  POST /webhook/stripe                          → Eventos de pago
  GET  /admin/professionals                     → Profesionistas por validar   (Canal 2)
  POST /admin/professionals/{id}/approve        → Aprobar cédula               (Canal 2)
  POST /admin/professionals/{id}/reject         → Rechazar cédula              (Canal 2)

Arranque en Railway (Settings → Deploy → Custom Start Command):
  uvicorn main:app --host 0.0.0.0 --port $PORT
"""
import json
import logging
import secrets
import uuid
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

import b2b
import conversation
import payments
from audit import claim_event
from config import get_settings
from crypto import pseudonymize_phone
from database import get_session, init_db
from feature_flags import b2b_enabled
from messages import t
from models import Professional, ProfessionalStatus, User
from whatsapp import Inbound, Out, WhatsAppClient, parse_inbound, text, verify_signature

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("nutri.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings()          # Valida todas las variables al arrancar
    await init_db()         # Crea tablas y triggers si no existen
    app.state.wa = WhatsAppClient()
    log.info("Nutri-IA lista")
    yield
    await app.state.wa.aclose()


# docs_url=None: no se publica la documentación automática en producción
app = FastAPI(title="Nutri-IA", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------
# WhatsApp
# ---------------------------------------------------------------------
@app.get("/webhook/whatsapp")
async def whatsapp_verify(request: Request):
    p = request.query_params
    expected = get_settings().wa_verify_token.get_secret_value()
    if p.get("hub.mode") == "subscribe" and secrets.compare_digest(p.get("hub.verify_token", ""), expected):
        return PlainTextResponse(p.get("hub.challenge", ""))
    raise HTTPException(status_code=403)


@app.post("/webhook/whatsapp")
async def whatsapp_receive(
    request: Request,
    background: BackgroundTasks,
    x_hub_signature_256: str | None = Header(default=None),
):
    raw = await request.body()
    if not verify_signature(raw, x_hub_signature_256):
        raise HTTPException(status_code=401)
    # Se responde 200 de inmediato; Meta reintenta si tardamos
    for inb in parse_inbound(json.loads(raw)):
        background.add_task(process_inbound, request.app.state.wa, inb)
    return {"status": "received"}


async def _get_or_create_user(session, wa_hash: str, phone: str) -> User:
    """Alta segura ante mensajes simultáneos del mismo número."""
    await session.execute(
        pg_insert(User)
        .values(id=uuid.uuid4(), wa_hash=wa_hash, wa_phone=phone)
        .on_conflict_do_nothing(index_elements=["wa_hash"])
    )
    return await session.scalar(select(User).where(User.wa_hash == wa_hash).with_for_update())


async def process_inbound(wa: WhatsAppClient, inb: Inbound) -> None:
    outs: list[Out] = []
    try:
        async with get_session() as session:
            if not await claim_event(session, "whatsapp", inb.message_id):
                return  # Mensaje duplicado (reintento de Meta)
            wa_hash = pseudonymize_phone(inb.phone)

            pro = None
            if await b2b_enabled(session):
                pro = await session.scalar(
                    select(Professional).where(Professional.wa_hash == wa_hash).with_for_update()
                )
            if pro is not None:
                outs = await b2b.handle_pro(session, pro, inb)
            else:
                user = await _get_or_create_user(session, wa_hash, inb.phone)
                outs = await conversation.handle(session, user, inb)
    except Exception:
        log.exception("Error procesando mensaje %s", inb.message_id)
        outs = [text(t("error_generic", "es"))]

    # Envío DESPUÉS de confirmar en BD
    for out in outs:
        try:
            await wa.send(out.to or inb.phone, out)
        except Exception:
            log.exception("No se pudo enviar un mensaje de WhatsApp")


# ---------------------------------------------------------------------
# Stripe
# ---------------------------------------------------------------------
@app.post("/webhook/stripe")
async def stripe_webhook(request: Request, stripe_signature: str | None = Header(default=None)):
    raw = await request.body()
    try:
        notifications = await payments.handle_stripe_event(raw, stripe_signature or "")
    except payments.InvalidStripeSignature:
        raise HTTPException(status_code=400)
    # Otros errores devuelven 500 → Stripe reintenta automáticamente

    wa: WhatsAppClient = request.app.state.wa
    for phone, out in notifications:
        try:
            await wa.send(phone, out)
        except Exception:
            log.exception("No se pudo notificar por WhatsApp tras evento de Stripe")
    return {"received": True}


# ---------------------------------------------------------------------
# Administración (Canal 2) — protegida con ADMIN_API_TOKEN
# ---------------------------------------------------------------------
def _require_admin(authorization: str | None) -> None:
    expected = f"Bearer {get_settings().admin_api_token.get_secret_value()}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401)


@app.get("/admin/professionals")
async def list_pending(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    async with get_session() as session:
        rows = (await session.scalars(
            select(Professional).where(Professional.status == ProfessionalStatus.PENDING_VALIDATION)
        )).all()
        return [
            {"id": str(p.id), "name": p.full_name, "email": p.email, "city": p.city, "cedula": p.cedula}
            for p in rows
        ]


@app.post("/admin/professionals/{pro_id}/approve")
async def approve_professional(pro_id: uuid.UUID, request: Request,
                               authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    async with get_session() as session:
        result = await b2b.approve(session, pro_id)
        if result is None:
            raise HTTPException(status_code=404, detail="No encontrado o no pendiente")
        pro, url = result
        phone, lang, price = pro.wa_phone, pro.language.value, b2b._price(pro.language.value)
    try:
        # Puede fallar si pasaron más de 24 h desde su último mensaje (regla de Meta)
        await request.app.state.wa.send(phone, text(t("pro_checkout", lang, price=price, url=url)))
        notified = True
    except Exception:
        notified = False
    return {"status": "approved", "checkout_url": url, "whatsapp_notified": notified}


@app.post("/admin/professionals/{pro_id}/reject")
async def reject_professional(pro_id: uuid.UUID, request: Request,
                              authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    async with get_session() as session:
        pro = await b2b.reject(session, pro_id)
        if pro is None:
            raise HTTPException(status_code=404, detail="No encontrado o no pendiente")
        phone, lang = pro.wa_phone, pro.language.value
    try:
        await request.app.state.wa.send(phone, text(t("pro_rejected", lang, email=get_settings().support_email)))
    except Exception:
        pass
    return {"status": "rejected"}
