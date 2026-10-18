"""
conversation.py — Máquina de estados del Canal 1 (usuarios).

Cada mensaje entrante: se lee el estado actual del usuario, se valida la
respuesta, se guarda, se avanza al siguiente estado y se devuelve la
pregunta siguiente (lista de Out). main.py envía esos mensajes DESPUÉS de
confirmar la transacción en la base de datos.

Orden del flujo:
  Idioma → [Rol, si Canal 2 activo] → Aviso de privacidad → Alias → Edad →
  Sexo → Peso → Estatura → Cintura → Actividad → Meta → Aviso educativo →
  Declaración bajo protesta → Flexi-Menú (4 categorías) → Pago → Guía →
  Check-in semanal
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import b2b
import checkin
from audit import log_event, record_consent
from config import get_settings
from feature_flags import b2b_enabled
from messages import t
from models import ActivityLevel, ConsentType, Goal, GuidePlan, HealthProfile, Language, Sex, User
from nutrition import bmi, item_title, menu_items, render
from payments import guide_checkout_url, load_plan
from states import S, parse_number
from whatsapp import Inbound, Out, buttons, list_menu, text

# Estado → (categoría del Flexi-Menú, estado siguiente)
FOOD_FLOW = {
    S.FOOD_PROTEIN: ("protein", S.FOOD_CARB),
    S.FOOD_CARB: ("carb", S.FOOD_VEG),
    S.FOOD_VEG: ("veg", S.FOOD_FLEX),
    S.FOOD_FLEX: ("flex", None),
}

# Rangos válidos: (mínimo, máximo, unidad)
RANGES = {S.WEIGHT: (30, 300, "kg"), S.HEIGHT: (120, 230, "cm"), S.WAIST: (40, 200, "cm")}


def _lang(user: User) -> str:
    return (user.language or Language.ES).value


def privacy_text(lang: str) -> str:
    s = get_settings()
    return t("privacy", lang, company=s.company_legal_name, email=s.support_email, url=s.privacy_notice_url)


def food_menu(state: str, lang: str, chosen: list[str]) -> list[Out]:
    category = FOOD_FLOW[state][0]
    items = menu_items(category)
    titles = {i.code: item_title(i, lang) for i in items}
    body = t(f"food_{category}", lang)
    if chosen:
        body += "\n" + t("food_chosen", lang, items=", ".join(titles[c] for c in chosen))
    rows = [(i.code, titles[i.code]) for i in items if i.code not in chosen]
    rows.append(("done", t("row_done", lang)))
    return [list_menu(body, t("btn_options", lang), rows)]


def ask(state: str, lang: str, chosen: list[str] | None = None) -> list[Out]:
    """Pregunta correspondiente a cada estado."""
    if state == S.LANG:
        return [buttons(t("choose_language", "es"), [("lang_es", "Español"), ("lang_en", "English")])]
    if state == S.ROLE:
        return [buttons(t("choose_role", lang),
                        [("role_user", t("role_user", lang)), ("role_pro", t("role_pro", lang))])]
    if state == S.PRIVACY:
        return [buttons(privacy_text(lang),
                        [("accept", t("btn_accept", lang)), ("decline", t("btn_decline", lang))])]
    if state == S.ALIAS:
        return [text(t("ask_alias", lang))]
    if state == S.AGE:
        return [text(t("ask_age", lang))]
    if state == S.SEX:
        return [buttons(t("ask_sex", lang),
                        [(Sex.FEMALE.value, t("sex_female", lang)), (Sex.MALE.value, t("sex_male", lang))])]
    if state == S.WEIGHT:
        return [text(t("ask_weight", lang))]
    if state == S.HEIGHT:
        return [text(t("ask_height", lang))]
    if state == S.WAIST:
        return [text(t("ask_waist", lang))]
    if state == S.ACTIVITY:
        return [list_menu(t("ask_activity", lang), t("btn_options", lang),
                          [(a.value, t(f"act_{a.value}", lang)) for a in ActivityLevel])]
    if state == S.GOAL:
        return [buttons(t("ask_goal", lang), [(g.value, t(f"goal_{g.value}", lang)) for g in Goal])]
    if state == S.DISCLAIMER:
        return [buttons(t("disclaimer", lang),
                        [("accept", t("btn_accept", lang)), ("decline", t("btn_decline", lang))])]
    if state == S.SWORN:
        return [buttons(t("sworn", lang),
                        [("yes", t("btn_yes_cond", lang)), ("no", t("btn_no_cond", lang))])]
    if state == S.REFERRAL_CITY:
        return [text(t("referral_ask_city", lang))]
    if state in FOOD_FLOW:
        return food_menu(state, lang, chosen or [])
    return []


async def get_profile(session: AsyncSession, user: User) -> HealthProfile:
    profile = await session.scalar(
        select(HealthProfile).where(HealthProfile.user_id == user.id).with_for_update()
    )
    if profile is None:
        profile = HealthProfile(id=uuid.uuid4(), user_id=user.id, food_choices={})
        session.add(profile)
    return profile


def _block(session: AsyncSession, user: User, reason: str) -> None:
    user.is_blocked = True
    user.blocked_reason = reason
    user.state = S.BLOCKED
    log_event(session, "user.blocked", user.id, reason=reason)


async def handle(session: AsyncSession, user: User, inb: Inbound) -> list[Out]:
    s = get_settings()
    lang = _lang(user)
    ans = (inb.reply_id or inb.text).strip()
    low = ans.lower()
    st = user.state

    if user.is_blocked:
        return [text(t("blocked", lang, email=s.support_email))]

    # ---------- Inicio e idioma ----------
    if st == S.START:
        user.state = S.LANG
        return ask(S.LANG, lang)

    if st == S.LANG:
        if ans == "lang_es" or low.startswith("es"):
            user.language = Language.ES
        elif ans == "lang_en" or low.startswith("en"):
            user.language = Language.EN
        else:
            return ask(S.LANG, lang)
        lang = user.language.value
        user.state = S.ROLE if await b2b_enabled(session) else S.PRIVACY
        return ask(user.state, lang)

    if st == S.ROLE:
        if ans == "role_pro":
            user.state = S.ROUTED_PRO
            return await b2b.start_registration(session, user)
        if ans == "role_user":
            user.state = S.PRIVACY
            return ask(S.PRIVACY, lang)
        return [text(t("use_buttons", lang))] + ask(S.ROLE, lang)

    if st == S.ROUTED_PRO:
        return [text(t("pro_unavailable", lang))]

    # ---------- Consentimiento (antes de cualquier dato sensible) ----------
    if st == S.PRIVACY:
        if ans not in ("accept", "decline"):
            return [text(t("use_buttons", lang))] + ask(S.PRIVACY, lang)
        accepted = ans == "accept"
        record_consent(session, user_id=user.id, consent_type=ConsentType.PRIVACY_NOTICE,
                       language=user.language, shown_text=privacy_text(lang),
                       response="ACCEPTED" if accepted else "DECLINED", wa_message_id=inb.message_id)
        if not accepted:
            user.state = S.START
            return [text(t("privacy_declined", lang))]
        user.state = S.ALIAS
        return ask(S.ALIAS, lang)

    profile = await get_profile(session, user)

    # ---------- Datos ----------
    if st == S.ALIAS:
        alias = inb.text.strip()
        if not 2 <= len(alias) <= 40:
            return [text(t("invalid_alias", lang))]
        user.alias = alias
        user.state = S.AGE
        return ask(S.AGE, lang)

    if st == S.AGE:
        n = parse_number(inb.text)
        if n is None or not 1 <= n <= 120:
            return [text(t("invalid_range", lang, lo=s.min_user_age, hi=s.max_user_age, unit=""))]
        age = int(n)
        if age < s.min_user_age:
            _block(session, user, "underage")   # La edad del menor NO se guarda
            return [text(t("underage", lang, min=s.min_user_age))]
        if age > s.max_user_age:
            _block(session, user, "age_over")
            return [text(t("age_over", lang, max=s.max_user_age))]
        profile.age = age
        user.state = S.SEX
        return ask(S.SEX, lang)

    if st == S.SEX:
        if ans not in (Sex.FEMALE.value, Sex.MALE.value):
            return [text(t("use_buttons", lang))] + ask(S.SEX, lang)
        profile.sex = Sex(ans)
        user.state = S.WEIGHT
        return ask(S.WEIGHT, lang)

    if st in RANGES:
        lo, hi, unit = RANGES[st]
        n = parse_number(inb.text)
        if n is not None and st == S.HEIGHT and n < 3:
            n *= 100  # Escribió metros (1.68) en vez de centímetros
        if n is None or not lo <= n <= hi:
            return [text(t("invalid_range", lang, lo=lo, hi=hi, unit=unit))]
        if st == S.WEIGHT:
            profile.weight_kg, user.state = n, S.HEIGHT
        elif st == S.HEIGHT:
            profile.height_cm, user.state = n, S.WAIST
        else:
            profile.waist_cm, user.state = n, S.ACTIVITY
        return ask(user.state, lang)

    if st == S.ACTIVITY:
        if ans not in {a.value for a in ActivityLevel}:
            return [text(t("use_buttons", lang))] + ask(S.ACTIVITY, lang)
        profile.activity_level = ActivityLevel(ans)
        user.state = S.GOAL
        return ask(S.GOAL, lang)

    if st == S.GOAL:
        if ans not in {g.value for g in Goal}:
            return [text(t("use_buttons", lang))] + ask(S.GOAL, lang)
        goal, outs = Goal(ans), []
        if goal == Goal.LOSE and bmi(profile.weight_kg, profile.height_cm) < 18.5:
            goal = Goal.MAINTAIN   # Seguridad: nunca un plan de pérdida con bajo peso
            outs.append(text(t("low_bmi_maintain", lang)))
        profile.goal = goal
        user.state = S.DISCLAIMER
        return outs + ask(S.DISCLAIMER, lang)

    # ---------- Aviso educativo y declaración bajo protesta ----------
    if st == S.DISCLAIMER:
        if ans not in ("accept", "decline"):
            return [text(t("use_buttons", lang))] + ask(S.DISCLAIMER, lang)
        accepted = ans == "accept"
        record_consent(session, user_id=user.id, consent_type=ConsentType.EDUCATIONAL_DISCLAIMER,
                       language=user.language, shown_text=t("disclaimer", lang),
                       response="ACCEPTED" if accepted else "DECLINED", wa_message_id=inb.message_id)
        if not accepted:
            return [text(t("disclaimer_declined", lang))] + ask(S.DISCLAIMER, lang)
        user.state = S.SWORN
        return ask(S.SWORN, lang)

    if st == S.SWORN:
        if ans not in ("yes", "no"):
            return [text(t("use_buttons", lang))] + ask(S.SWORN, lang)
        record_consent(session, user_id=user.id, consent_type=ConsentType.SWORN_STATEMENT,
                       language=user.language, shown_text=t("sworn", lang),
                       response=ans.upper(), wa_message_id=inb.message_id)
        if ans == "yes":
            if await b2b_enabled(session):
                user.state = S.REFERRAL_CITY
                return ask(S.REFERRAL_CITY, lang)
            _block(session, user, "pathology")
            return [text(t("pathology_block", lang))]
        user.state = S.FOOD_PROTEIN
        return [text(t("food_intro", lang))] + ask(S.FOOD_PROTEIN, lang, [])

    if st == S.REFERRAL_CITY:
        return await b2b.refer_user(session, user, inb.text, lang)

    # ---------- Flexi-Menú ----------
    if st in FOOD_FLOW:
        category, next_state = FOOD_FLOW[st]
        choices = dict(profile.food_choices or {})
        chosen = list(choices.get(category, []))
        valid = {i.code for i in menu_items(category)}

        if ans == "done":
            if not chosen and category != "flex":
                return [text(t("food_need_one", lang))] + ask(st, lang, chosen)
            if next_state:
                user.state = next_state
                return ask(next_state, lang, choices.get(FOOD_FLOW[next_state][0], []))
            # Fin del menú → pago
            url = await guide_checkout_url(session, user)
            user.state = S.AWAITING_PAYMENT
            price = s.guide_price_label_en if lang == "en" else s.guide_price_label_es
            return [text(t("payment_link", lang, weeks=s.followup_weeks, price=price, url=url))]

        if ans in valid and ans not in chosen:
            chosen.append(ans)
            choices[category] = chosen
            profile.food_choices = choices  # Nuevo dict para que SQLAlchemy detecte el cambio
        return ask(st, lang, chosen)

    # ---------- Post-pago ----------
    if st == S.AWAITING_PAYMENT:
        url = await guide_checkout_url(session, user)
        return [text(t("awaiting_payment", lang, url=url))]

    if st == S.ACTIVE:
        if low in ("guia", "guía", "guide"):
            plan_row = await session.scalar(
                select(GuidePlan).where(GuidePlan.user_id == user.id)
                .order_by(GuidePlan.created_at.desc()).limit(1)
            )
            if plan_row:
                return [text(render(load_plan(plan_row.plan), lang, user.alias))]
        return [text(t("active_status", lang))]

    if st == S.CHECKIN_WEIGHT:
        return await checkin.process_checkin(session, user, profile, inb, lang)

    if st == S.FINISHED:
        return [text(t("followup_ended", lang))]

    # Estado desconocido: reinicio seguro
    user.state = S.LANG
    return ask(S.LANG, lang)
