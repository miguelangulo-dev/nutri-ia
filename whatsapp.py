"""
whatsapp.py — Cliente de WhatsApp Cloud API (Meta).

- verify_signature(): confirma que el webhook viene de Meta (firma HMAC).
- parse_inbound(): convierte el JSON de Meta en objetos Inbound simples.
- Out / text / buttons / list_menu: mensajes de salida. Los manejadores de
  conversación DEVUELVEN Out y main.py los envía DESPUÉS de guardar en BD,
  así un fallo de red nunca deja la base de datos a medias.

Límites de WhatsApp respetados aquí: 3 botones (20 caracteres c/u), listas
de 10 filas (24 caracteres), cuerpo interactivo de 1024 y texto de 4096.
"""
import hashlib
import hmac
import logging
from dataclasses import dataclass, field

import httpx

from config import get_settings

log = logging.getLogger("nutri.whatsapp")

GRAPH_URL = "https://graph.facebook.com"
MAX_TEXT = 4096
MAX_INTERACTIVE_BODY = 1024


@dataclass
class Inbound:
    phone: str
    message_id: str
    text: str = ""
    reply_id: str = ""   # ID del botón o fila elegida


@dataclass
class Out:
    kind: str                                   # text | buttons | list | template
    body: str = ""
    buttons: list[tuple[str, str]] = field(default_factory=list)
    button_label: str = ""
    rows: list[tuple[str, str]] = field(default_factory=list)
    template: str = ""
    template_lang: str = ""
    to: str | None = None                       # None = responder a quien escribió


def text(body: str) -> Out:
    return Out("text", body=body)


def buttons(body: str, options: list[tuple[str, str]]) -> Out:
    return Out("buttons", body=body, buttons=options)


def list_menu(body: str, label: str, rows: list[tuple[str, str]]) -> Out:
    return Out("list", body=body, button_label=label, rows=rows)


def verify_signature(raw_body: bytes, header: str | None) -> bool:
    """Meta firma cada webhook con tu App Secret (encabezado X-Hub-Signature-256)."""
    if not header or not header.startswith("sha256="):
        return False
    secret = get_settings().wa_app_secret.get_secret_value().encode()
    expected = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[7:])


def parse_inbound(payload: dict) -> list[Inbound]:
    """Extrae los mensajes entrantes. Ignora estados de entrega (sent/read)."""
    result: list[Inbound] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for m in change.get("value", {}).get("messages", []) or []:
                inb = Inbound(phone=m.get("from", ""), message_id=m.get("id", ""))
                mtype = m.get("type")
                if mtype == "text":
                    inb.text = m.get("text", {}).get("body", "").strip()
                elif mtype == "interactive":
                    it = m.get("interactive", {})
                    reply = it.get("button_reply") or it.get("list_reply") or {}
                    inb.reply_id = reply.get("id", "")
                    inb.text = reply.get("title", "")
                elif mtype == "button":  # Respuesta rápida de una plantilla
                    inb.text = m.get("button", {}).get("text", "")
                    inb.reply_id = m.get("button", {}).get("payload", "")
                if inb.phone and inb.message_id:
                    result.append(inb)
    return result


def split_text(body: str, limit: int = MAX_TEXT) -> list[str]:
    """Parte textos largos por párrafos para no exceder el límite de WhatsApp."""
    if len(body) <= limit:
        return [body]
    chunks, current = [], ""
    for para in body.split("\n\n"):
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = para[:limit]
    if current:
        chunks.append(current)
    return chunks


class WhatsAppClient:
    def __init__(self) -> None:
        s = get_settings()
        self._url = f"{GRAPH_URL}/{s.wa_api_version}/{s.wa_phone_number_id}/messages"
        self._http = httpx.AsyncClient(
            timeout=15,
            headers={"Authorization": f"Bearer {s.wa_access_token.get_secret_value()}"},
        )

    async def _post(self, to: str, payload: dict) -> None:
        body = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, **payload}
        r = await self._http.post(self._url, json=body)
        if r.status_code >= 400:
            # Nunca se registra el número; solo el error de Meta
            log.error("WhatsApp API %s: %s", r.status_code, r.text[:500])
            r.raise_for_status()

    async def send(self, to: str, out: Out) -> None:
        if out.kind == "text":
            for chunk in split_text(out.body):
                await self._post(to, {"type": "text", "text": {"body": chunk, "preview_url": True}})
            return

        if out.kind == "template":
            await self._post(to, {
                "type": "template",
                "template": {"name": out.template, "language": {"code": out.template_lang}},
            })
            return

        # Mensajes interactivos: si el texto es largo, va antes como texto normal
        body = out.body
        if len(body) > MAX_INTERACTIVE_BODY:
            await self.send(to, text(body))
            body = "👇"

        if out.kind == "buttons":
            interactive = {
                "type": "button",
                "body": {"text": body},
                "action": {"buttons": [
                    {"type": "reply", "reply": {"id": i, "title": t[:20]}} for i, t in out.buttons[:3]
                ]},
            }
        elif out.kind == "list":
            interactive = {
                "type": "list",
                "body": {"text": body},
                "action": {
                    "button": out.button_label[:20],
                    "sections": [{
                        "title": out.button_label[:24],
                        "rows": [{"id": i, "title": t[:24]} for i, t in out.rows[:10]],
                    }],
                },
            }
        else:
            raise ValueError(f"Tipo de mensaje desconocido: {out.kind}")

        await self._post(to, {"type": "interactive", "interactive": interactive})

    async def aclose(self) -> None:
        await self._http.aclose()
